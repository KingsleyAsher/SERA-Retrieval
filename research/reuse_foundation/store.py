"""Isolated immutable snapshots, source events and deduplicated vector payloads."""
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .common import Ledger, digest, normalized, packed
from .sources import STATES


@dataclass(frozen=True)
class Snapshot:
    identity: str
    epoch: int
    owner: str
    rows_json: str

    @property
    def rows(self):
        return json.loads(self.rows_json)


def validate(record):
    r = dict(record)
    for key in ('namespace', 'id', 'version', 'text', 'content_sha', 'path', 'scope',
                'policy_revision', 'preprocessing'):
        if not isinstance(r.get(key), str) or (key != 'text' and not r[key]):
            raise ValueError(f'missing or invalid {key}')
    if type(r.get('visible')) is not bool or r.get('status') not in STATES:
        raise ValueError('explicit visibility/lifecycle required')
    if r['content_sha'] != digest(r['text']):
        raise ValueError('content hash mismatch')
    r.setdefault('provenance', {})
    if not isinstance(r['provenance'], dict):
        raise ValueError('provenance must be an object')
    vector = r.pop('vector', None)
    raw = None
    if vector is not None:
        if not isinstance(r.get('model'), str) or not r['model']:
            raise ValueError('vector model missing')
        v, original = normalized(vector, r.get('dtype'))
        if type(r.get('dimension')) is not int or len(v) != r['dimension']:
            raise ValueError('vector dimension mismatch')
        raw = v.astype('<f8').tobytes()
        r.update(vector_sha=digest(raw), original_vector_sha=original,
                 conversion='fp32_to_normalized_f64_v1' if r['dtype'] == 'float32' else 'canonical_f64_identity_v1')
        claimed = r['provenance'].get('raw_vector_sha')
        if claimed and original != claimed:
            raise ValueError('raw vector hash mismatch')
    else:
        r.update(vector_sha=None, original_vector_sha=None, conversion=None)
    packed(r)  # Reject non-serializable/nonfinite provenance before any write.
    return r, raw


class FoundationStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables and ('reuse_meta' not in tables or any(not name.startswith('reuse_') for name in tables)):
            self.db.close()
            raise ValueError('target is not an isolated reuse foundation database')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS reuse_meta(key TEXT PRIMARY KEY,value TEXT);
          CREATE TABLE IF NOT EXISTS reuse_current(key TEXT PRIMARY KEY,record TEXT NOT NULL,serial INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS reuse_vectors(hash TEXT PRIMARY KEY,data BLOB NOT NULL);
          CREATE TABLE IF NOT EXISTS reuse_snapshots(id TEXT PRIMARY KEY,epoch INTEGER,rows TEXT);
          CREATE TABLE IF NOT EXISTS reuse_operations(id TEXT PRIMARY KEY,digest TEXT,snapshot TEXT);
          CREATE TABLE IF NOT EXISTS reuse_checkpoints(id TEXT PRIMARY KEY,payload TEXT);
        ''')
        self.db.execute("INSERT OR IGNORE INTO reuse_meta VALUES('instance',?)", (str(uuid.uuid4()),))
        self.db.execute("INSERT OR IGNORE INTO reuse_meta VALUES('epoch','0')")
        instance = self.db.execute("SELECT value FROM reuse_meta WHERE key='instance'").fetchone()[0]
        self.owner = digest(instance + str(self.path))

    @staticmethod
    def key(r):
        return packed([r['namespace'], r['id']])

    def _current(self):
        return [dict(json.loads(r), serial=s) for r, s in self.db.execute('SELECT record,serial FROM reuse_current ORDER BY key')]

    @property
    def epoch(self):
        with self.lock:
            return int(self.db.execute("SELECT value FROM reuse_meta WHERE key='epoch'").fetchone()[0])

    def current(self):
        with self.lock:
            return self._current()

    def _publish(self):
        epoch = self.epoch + 1
        self.db.execute("UPDATE reuse_meta SET value=? WHERE key='epoch'", (str(epoch),))
        rows = packed(self._current())
        identity = digest(packed([self.owner, epoch, rows]))
        self.db.execute('INSERT INTO reuse_snapshots VALUES(?,?,?)', (identity, epoch, rows))
        return identity

    def snapshot(self, identity=None):
        with self.lock:
            if identity is None:
                row = self.db.execute('SELECT id,epoch,rows FROM reuse_snapshots ORDER BY epoch DESC LIMIT 1').fetchone()
            else:
                row = self.db.execute('SELECT id,epoch,rows FROM reuse_snapshots WHERE id=?', (identity,)).fetchone()
            if row is None:
                raise ValueError('unknown or empty snapshot')
            return Snapshot(row[0], row[1], self.owner, row[2])

    def vector(self, row, ledger, prepaid=False):
        dimension = row['dimension']
        if not prepaid:
            ledger.charge(vector_logical_bytes=dimension * 8)
        with self.lock:
            found = self.db.execute('SELECT data FROM reuse_vectors WHERE hash=?', (row['vector_sha'],)).fetchone()
        if not found or len(found[0]) != dimension * 8 or digest(found[0]) != row['vector_sha']:
            raise ValueError('vector payload integrity failure')
        return np.frombuffer(found[0], dtype='<f8').copy()

    def apply_events(self, events, ledger=None):
        """Replay explicit state changes. One batch is atomic and idempotent."""
        if not events or len({e['event_id'] for e in events}) != len(events):
            raise ValueError('nonempty batch with unique event IDs required')
        allowed = {'change', 'correct', 'withdraw', 'delete', 'permissions', 'pending', 'activate'}
        ledger = ledger or Ledger()
        ledger.charge(maintenance_events=len(events), maintenance_input_bytes=len(packed(events).encode()),
                      state_commits=1)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                fresh = []
                for event in events:
                    if event['action'] not in allowed:
                        raise ValueError('unknown event action')
                    fingerprint = digest(packed(event))
                    operation = 'event:' + event['event_id']
                    old = self.db.execute('SELECT digest FROM reuse_operations WHERE id=?', (operation,)).fetchone()
                    if old and old[0] != fingerprint:
                        raise ValueError('event identity conflict')
                    if not old:
                        fresh.append((event, fingerprint, operation))
                for event, _, _ in fresh:
                    key = packed([event['namespace'], event['id']])
                    ledger.charge(metadata_checks=1)
                    previous = self.db.execute('SELECT record,serial FROM reuse_current WHERE key=?', (key,)).fetchone()
                    if previous is None:
                        raise ValueError('event source missing')
                    r, serial = json.loads(previous[0]), previous[1]
                    action = event['action']
                    if action in ('change', 'correct'):
                        new, raw = validate(event['record'])
                        if self.key(new) != key or new['version'] == r['version']:
                            raise ValueError('replacement requires same identity and a new version')
                        r = new
                        if raw is not None:
                            ledger.charge(vector_write_bytes=len(raw))
                            self.db.execute('INSERT OR IGNORE INTO reuse_vectors VALUES(?,?)', (r['vector_sha'], raw))
                    elif action == 'permissions':
                        if type(event['visible']) is not bool or not isinstance(event['policy_revision'], str) or not event['policy_revision'] or event['policy_revision'] == r['policy_revision']:
                            raise ValueError('new explicit permission revision required')
                        r.update(visible=event['visible'], policy_revision=event['policy_revision'])
                        if 'scope' in event:
                            if not isinstance(event['scope'], str) or not event['scope']:
                                raise ValueError('scope required')
                            r['scope'] = event['scope']
                    else:
                        r['status'] = {'withdraw': 'withdrawn', 'delete': 'deleted', 'pending': 'pending', 'activate': 'active'}[action]
                        if action == 'delete':
                            r['visible'] = False
                    payload = packed(r)
                    ledger.charge(maintenance_record_bytes=len(payload.encode()))
                    self.db.execute('UPDATE reuse_current SET record=?,serial=? WHERE key=?', (payload, serial + 1, key))
                identity = self._publish() if fresh else self.snapshot().identity
                for _, fingerprint, operation in fresh:
                    self.db.execute('INSERT INTO reuse_operations VALUES(?,?,?)', (operation, fingerprint, identity))
                self.db.execute('COMMIT')
                return self.snapshot(identity)
            except Exception:
                self.db.execute('ROLLBACK')
                raise

    def close(self):
        self.db.close()


def import_snapshot(records, store, ledger=None):
    ledger = ledger or Ledger()
    envelope = records if isinstance(records, dict) else {'format': 1, 'records': records}
    if envelope.get('format') != 1:
        raise ValueError('unsupported export format')
    staged = [validate(r) for r in envelope['records']]
    ledger.charge(import_records=len(staged), import_vector_bytes=sum(len(raw) for _, raw in staged if raw))
    keys = [store.key(r) for r, _ in staged]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate source identities')
    # A vector namespace cannot silently mix dimensions or preprocessing.
    namespaces = {}
    for r, _ in staged:
        if r['vector_sha']:
            signature = (r['model'], r['dimension'], r['preprocessing'], r['conversion'])
            old = namespaces.setdefault(r['namespace'], signature)
            if old != signature:
                raise ValueError('mixed representation namespace')
    fingerprint = digest(packed([envelope.get('source_manifest'), sorted((r for r, _ in staged), key=store.key)]))
    operation = 'import:' + fingerprint
    with store.lock:
        store.db.execute('BEGIN IMMEDIATE')
        try:
            prior = store.db.execute('SELECT snapshot FROM reuse_operations WHERE id=?', (operation,)).fetchone()
            if prior:
                store.db.execute('ROLLBACK')
                return dict(snapshot=prior[0], idempotent=True, records=len(staged), resources=ledger.dump())
            ledger.charge(state_commits=1)
            # Imports are complete source snapshots. Missing members become tombstones.
            imported_names = {r['namespace'] for r, _ in staged}
            if envelope.get('source_manifest', {}).get('namespace'):
                imported_names.add(envelope['source_manifest']['namespace'])
            previous = {store.key(r): r for r in store._current()}
            for key, old in previous.items():
                if old['namespace'] in imported_names and key not in keys:
                    serial = old.pop('serial')
                    old.update(status='deleted', visible=False)
                    store.db.execute('UPDATE reuse_current SET record=?,serial=? WHERE key=?', (packed(old), serial + 1, key))
            for r, raw in staged:
                key = store.key(r)
                old = previous.get(key)
                if old:
                    serial = old.pop('serial', 0)
                    if old['version'] == r['version'] and old['content_sha'] != r['content_sha']:
                        raise ValueError('content changed without source version change')
                    serial += int(old != r)
                else:
                    serial = 1
                store.db.execute('INSERT OR REPLACE INTO reuse_current VALUES(?,?,?)', (key, packed(r), serial))
                if raw is not None:
                    store.db.execute('INSERT OR IGNORE INTO reuse_vectors VALUES(?,?)', (r['vector_sha'], raw))
            identity = store._publish()
            store.db.execute('INSERT INTO reuse_operations VALUES(?,?,?)', (operation, fingerprint, identity))
            store.db.execute('COMMIT')
            return dict(snapshot=identity, idempotent=False, records=len(staged),
                        missing_vectors=sum(r['vector_sha'] is None for r, _ in staged),
                        source_manifest=envelope.get('source_manifest'), resources=ledger.dump())
        except Exception:
            store.db.execute('ROLLBACK')
            raise
