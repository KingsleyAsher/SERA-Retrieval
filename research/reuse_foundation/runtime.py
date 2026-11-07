"""Dependency guards, byte-bounded retention and cooperative async work lanes."""
import asyncio
import os
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .common import digest, packed


class Cancelled(Exception):
    pass


class Stale(Exception):
    pass


@dataclass(frozen=True)
class DependencyStamp:
    owner: str
    entries: tuple
    scopes: tuple
    historical: bool
    epoch: int | None


def capture_dependencies(store, rows, scopes=('global',), historical=False, universe=False):
    with store.lock:
        own_transaction = not store.db.in_transaction
        if own_transaction:
            store.db.execute('BEGIN')
        try:
            current = {store.key(r): r for r in store.current()}
            entries = []
            for row in rows:
                key = store.key(row)
                live = current.get(key)
                if live is None or not live['visible'] or live['scope'] not in scopes or live['status'] == 'deleted':
                    raise Stale('source inaccessible')
                if not historical and (live['status'] != 'active' or live != row):
                    raise Stale('source is no longer current')
                entries.append((key, live['serial'], digest(packed(live))))
            return DependencyStamp(store.owner, tuple(sorted(entries)), tuple(sorted(scopes)),
                                   historical, store.epoch if universe else None)
        finally:
            if own_transaction:
                store.db.execute('ROLLBACK')


def validate_dependencies(store, stamp, ledger=None):
    if ledger:
        ledger.charge(metadata_checks=len(stamp.entries))
    with store.lock:
        if stamp.owner != store.owner or stamp.epoch is not None and stamp.epoch != store.epoch:
            return False
        if stamp.epoch is not None:
            # All mutations advance the epoch in the same SQLite transaction.
            return True
        current = {store.key(r): r for r in store.current()}
        for key, serial, fingerprint in stamp.entries:
            row = current.get(key)
            if (not row or row['serial'] != serial or digest(packed(row)) != fingerprint or
                not row['visible'] or row['scope'] not in stamp.scopes or
                row['status'] == 'deleted' or not stamp.historical and row['status'] != 'active'):
                return False
        return True


class ByteCache:
    """Retained byte payloads only; this is not a process/native-index memory cap."""
    def __init__(self, max_bytes=64 * 1024 * 1024):
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError('nonnegative byte budget required')
        self.max_bytes, self.used, self.evictions, self.bypasses = max_bytes, 0, 0, 0
        self.data = OrderedDict()
        self.hits, self.misses, self.read_bytes = 0, 0, 0
        self.lock = threading.RLock()

    def get(self, key):
        with self.lock:
            if key not in self.data:
                self.misses += 1
                return None
            value, cost = self.data.pop(key)
            self.data[key] = (value, cost)
            self.hits += 1
            self.read_bytes += len(value)
            return value

    def put(self, key, value):
        if not isinstance(key, str) or not isinstance(value, bytes):
            raise TypeError('cache requires string keys and immutable bytes')
        cost = len(key.encode()) + len(value)
        with self.lock:
            if key in self.data:
                self.used -= self.data.pop(key)[1]
            if cost > self.max_bytes:
                self.bypasses += 1
                return False
            while self.used + cost > self.max_bytes:
                _, (_, old) = self.data.popitem(last=False)
                self.used -= old
                self.evictions += 1
            self.data[key] = (value, cost)
            self.used += cost
            return True

    def stats(self):
        return dict(entries=len(self.data), payload_key_bytes=self.used,
                    max_bytes=self.max_bytes, evictions=self.evictions, bypasses=self.bypasses,
                    hits=self.hits, misses=self.misses, observed_cache_read_bytes=self.read_bytes)


class Resources:
    def __init__(self, store, cache_bytes=64 * 1024 * 1024):
        self.store, self.cache = store, ByteCache(cache_bytes)
        self.condition = asyncio.Condition()
        self.foregrounds, self.background_busy = 0, False
        self.flights = {}

    async def foreground(self, work):
        async with self.condition:
            self.foregrounds += 1
        try:
            return await work()
        finally:
            async with self.condition:
                self.foregrounds -= 1
                self.condition.notify_all()

    async def checkpoint(self):
        await asyncio.sleep(0)
        async with self.condition:
            await self.condition.wait_for(lambda: not self.foregrounds)

    async def background(self, work):
        async with self.condition:
            await self.condition.wait_for(lambda: not self.background_busy and not self.foregrounds)
            self.background_busy = True
        try:
            return await work(self.checkpoint)
        finally:
            async with self.condition:
                self.background_busy = False
                self.condition.notify_all()

    async def run_shared(self, key, stamp, work, ledger):
        """Only byte computations coalesce, never contexts with different dependencies.

        The producer's parent ledger pays physical work; waiters pay their own
        lookup/verification/wait counts. Shielding isolates one waiter's cancel.
        """
        if not validate_dependencies(self.store, stamp, ledger):
            raise Stale('invalid input dependencies')
        flight_key = digest(packed([key, stamp.__dict__]))
        ledger.charge(cache_lookups=1)
        cached = self.cache.get(flight_key)
        if cached is not None:
            ledger.charge(cache_payload_bytes=len(cached))
            if not validate_dependencies(self.store, stamp, ledger):
                raise Stale('cached dependencies changed')
            return cached
        item = self.flights.get(flight_key)
        if item is None:
            async def produce():
                result = await work()
                if not isinstance(result, bytes):
                    raise TypeError('shared computation must return bytes')
                if not item['waiters']:
                    raise Cancelled('all shared computation waiters cancelled')
                # Lock validation and publication against source mutations.
                with self.store.lock:
                    if not validate_dependencies(self.store, stamp, ledger):
                        raise Stale('computation invalidated before publication')
                    ledger.charge(cache_fill_bytes=len(result), cache_fills=1)
                    self.cache.put(flight_key, result)
                return result
            item = dict(task=asyncio.create_task(produce()), waiters=0)
            self.flights[flight_key] = item
            item['task'].add_done_callback(lambda t: None if t.cancelled() else t.exception())
        else:
            ledger.charge(coalesced_waits=1)
        item['waiters'] += 1
        try:
            value = await asyncio.shield(item['task'])
            if not validate_dependencies(self.store, stamp, ledger):
                raise Stale('computation invalidated before return')
            return value
        finally:
            item['waiters'] -= 1
            if item['waiters'] == 0:
                if not item['task'].done():
                    item['task'].cancel()
                if self.flights.get(flight_key) is item:
                    del self.flights[flight_key]


def atomic_publish(path, value, *, guard=lambda: True, cancel=None, sync=os.fsync,
                   replace=os.replace, publication_lock=None):
    """Publish a single self-contained manifest; old referenced assets stay live.

    sync/replace injection enables ordinary I/O failure checks. No claim of
    power-loss durability or atomicity across independent source stores.
    """
    from contextlib import nullcontext
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.tmp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(packed(value).encode())
            f.flush()
            sync(f.fileno())
        with publication_lock or nullcontext():
            if cancel and cancel.is_set():
                raise Cancelled('publication cancelled')
            if not guard():
                raise Stale('publication dependencies changed')
            replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
