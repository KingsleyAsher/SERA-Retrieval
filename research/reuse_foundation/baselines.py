"""Shared scoped inputs, canonical exact scanning and frozen USearch integration."""
import heapq
import json
import time
from types import SimpleNamespace

import numpy as np

from .common import SCORE, Ledger, Exhausted, canonical, digest, framework, packed
from .runtime import ByteCache, Cancelled, Stale, capture_dependencies, validate_dependencies

HARD_COUNTERS = {'canonical_scores', 'vector_logical_bytes', 'metadata_checks',
                 'source_reads', 'source_logical_bytes', 'state_commits', 'ann_calls',
                 'index_builds', 'index_input_vector_bytes', 'cache_lookups'}
HARD_COUNTERS |= {'maintenance_events', 'maintenance_input_bytes', 'maintenance_record_bytes',
                  'vector_write_bytes', 'import_records', 'import_vector_bytes',
                  'cache_fills', 'cache_fill_bytes', 'coalesced_waits', 'cache_payload_bytes'}


class Baselines:
    def __init__(self, store, cache_bytes=64 * 1024 * 1024):
        self.store, self.cache = store, ByteCache(cache_bytes)
        self.engines = {}  # Native index/matrix memory is reported separately from ByteCache.

    def _vector(self, row, ledger, admitted=False):
        if not admitted:
            ledger.charge(vector_logical_bytes=row['dimension'] * 8, cache_lookups=1)
        key = row['vector_sha']
        raw = self.cache.get(key)
        if raw is None:
            # Admission above covers the logical payload regardless of retention.
            raw = self.store.vector(row, ledger, prepaid=True).tobytes()
            self.cache.put(key, raw)
        else:
            if digest(raw) != key:
                raise ValueError('cached vector integrity failure')
        return np.frombuffer(raw, dtype='<f8')

    def run(self, query, *, backend='exact', k=10, window=256, scopes=('global',),
            snapshot=None, historical=False, limits=None, state=None, ledger=None, cancel=None):
        start = time.perf_counter()
        if backend not in ('exact', 'ann') or type(k) is not int or k < 1 or type(window) is not int or window < 1:
            raise ValueError('invalid backend, k or window')
        if not scopes or any(not isinstance(s, str) or not s for s in scopes):
            raise ValueError('explicit nonempty access scopes required')
        snap = self.store.snapshot(snapshot)
        if snap.owner != self.store.owner or not historical and snap.epoch != self.store.epoch:
            raise Stale('current query requires latest snapshot')
        all_rows = snap.rows
        current = {self.store.key(r): r for r in self.store.current()}
        accessible = [r for r in all_rows if r['visible'] and r['scope'] in scopes and
                      (historical or r['status'] == 'active') and r['status'] != 'deleted' and
                      (live := current.get(self.store.key(r))) and live['visible'] and
                      live['scope'] in scopes and live['status'] != 'deleted']
        rows = [r for r in accessible if r['vector_sha']]
        signatures = {(r['model'], r['preprocessing'], r['dimension'], r['conversion']) for r in rows}
        if len(signatures) > 1:
            raise ValueError('select scopes with one compatible vector namespace')
        q = np.asarray(query, dtype=np.float64).copy()
        if q.ndim != 1 or not len(q) or not np.isfinite(q).all() or abs(np.linalg.norm(q) - 1) > 1e-8:
            raise ValueError('finite normalized canonical query required')
        if rows and rows[0]['dimension'] != len(q):
            raise ValueError('query dimension mismatch')
        ids = [int(digest(self.store.key(r))[:15], 16) for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('stable numeric ID collision')
        signature = digest(packed([snap.identity, digest(q.tobytes()), backend, k, window,
                                   sorted(scopes), historical, SCORE]))
        limits = dict(limits or (ledger.limits if ledger else {}))
        if any(key not in HARD_COUNTERS or type(n) is not int or n < 0 for key, n in limits.items()):
            raise ValueError('unsupported hard budget; native ANN counters are observations only')
        if state and (state['signature'] != signature or state['owner'] != self.store.owner):
            raise ValueError('checkpoint request/owner mismatch')
        if state and packed(self.restore(signature)) != packed(state):
            raise ValueError('checkpoint payload differs from committed state')
        if state and any(state['consumed'].get(key, 0) > value for key, value in limits.items()):
            raise ValueError('resume below already consumed budget')
        if ledger and state and ledger.consumed != state['consumed']:
            raise ValueError('parent ledger must match checkpoint cumulative consumption')
        parent = ledger or Ledger(limits, state['consumed'] if state else None)
        if parent.limits != limits:
            raise ValueError('parent ledger limits mismatch')
        st = json.loads(packed(state)) if state else dict(signature=signature, owner=self.store.owner,
            cursor=0, heap=[], phase='prepare', candidates=None, source_cursor=0, items=[], consumed={})
        st['heap'] = [tuple(item) for item in st['heap']]
        checkpoint_admitted = False
        stamp = capture_dependencies(self.store, accessible, scopes, historical, universe=True)
        if not historical and stamp.epoch != snap.epoch:
            raise Stale('snapshot changed during request preparation')

        def guard():
            if cancel and cancel.is_set():
                raise Cancelled('query cancelled')
            if not validate_dependencies(self.store, stamp):
                raise Stale('source dependencies changed')

        def offer(pos, score):
            item = (float(score), -ids[pos], pos)
            if len(st['heap']) < k:
                heapq.heappush(st['heap'], item)
            elif item > st['heap'][0]:
                heapq.heapreplace(st['heap'], item)

        outcome = 'complete'
        reason = ''
        try:
            parent.charge(state_commits=1)
            checkpoint_admitted = True
            guard()
            if st['phase'] == 'prepare':
                parent.charge(metadata_checks=len(all_rows))
                st['phase'] = 'scan' if backend == 'exact' else 'ann'
            if st['phase'] == 'ann':
                key = snap.identity + ':' + digest(packed(ids))
                engine = self.engines.get(key)
                charge = dict(ann_calls=1) if rows else {}
                if engine is None and rows:
                    charge.update(vector_logical_bytes=len(rows) * len(q) * 8,
                                  cache_lookups=len(rows), index_builds=1,
                                  index_input_vector_bytes=len(rows) * len(q) * 4)
                parent.charge(**charge)
                if engine is None and rows:
                    vectors = np.stack([self._vector(r, parent, admitted=True) for r in rows])
                    fake = SimpleNamespace(namespace=self.store.owner, dim=len(q), model=rows[0]['model'])
                    reference = framework.Snapshot(snap.identity, snap.epoch, fake.model,
                        np.asarray(ids, dtype=np.int64), vectors, rows, 0, vectors.nbytes, self.store.owner)
                    engine = framework.Engine(fake, reference, candidates=max(50, k))
                    # Prior admission includes all known build costs, atomically.
                    engine.ensure_ann(np.arange(len(rows), dtype=np.int64), parent, prepaid=True)
                    self.engines.clear()  # Retain at most one native baseline index.
                    self.engines[key] = engine
                guard()
                if rows:
                    index = next(iter(engine.ann.values()))
                    found = index.search(q.astype(np.float32), count=min(max(50, k), len(rows)), threads=1)
                    st['candidates'] = [int(key) for key in found.keys]
                    st['ann_observed'] = dict(computed_distances=int(found.computed_distances),
                                              visited_members=int(found.visited_members))
                else:
                    st['candidates'] = []
                st['phase'] = 'scan'
            if st['phase'] == 'scan':
                positions = st['candidates'] if backend == 'ann' else range(len(rows))
                while st['cursor'] < len(positions):
                    guard()
                    # Compute only the admitted prefix. A pending return keeps
                    # both heap and cursor, so normal resume scores no item twice.
                    remaining = parent.limits.get('canonical_scores', float('inf')) - parent.consumed.get('canonical_scores', 0)
                    n = int(min(window, len(positions) - st['cursor'], remaining))
                    if n <= 0:
                        raise Exhausted('canonical_scores')
                    batch = list(positions[st['cursor']:st['cursor'] + n])
                    # Admit scores and vector reads together before either action.
                    parent.charge(canonical_scores=n, vector_logical_bytes=n * len(q) * 8, cache_lookups=n)
                    vectors = np.stack([self._vector(rows[p], parent, admitted=True) for p in batch])
                    scores = canonical(vectors, q)
                    for p, value in zip(batch, scores):
                        offer(p, value)
                    st['cursor'] += n
                st['selected'] = [p for _, _, p in sorted(st['heap'], reverse=True)]
                st['phase'] = 'sources'
            if st['phase'] == 'sources':
                scores = {p: score for score, _, p in st['heap']}
                while st['source_cursor'] < len(st['selected']):
                    guard()
                    pos = st['selected'][st['source_cursor']]
                    r = rows[pos]
                    parent.charge(source_reads=1, source_logical_bytes=len(r['text'].encode()))
                    st['items'].append(dict(id=ids[pos], namespace=r['namespace'], source_id=r['id'],
                        version=r['version'], status=r['status'], content_sha=r['content_sha'],
                        historical=historical, current_status=current[self.store.key(r)]['status'],
                        score=scores[pos], text=r['text']))
                    st['source_cursor'] += 1
                st['phase'] = 'done'
            guard()
        except Exhausted as exc:
            outcome, reason = 'pending', str(exc)
        except (Cancelled, Stale) as exc:
            outcome, reason = 'cancelled' if isinstance(exc, Cancelled) else 'stale', str(exc)
        st['consumed'] = parent.consumed.copy()
        persisted = False
        with self.store.lock:
            if outcome in ('complete', 'pending'):
                try:
                    guard()
                except (Cancelled, Stale) as exc:
                    outcome, reason = 'cancelled' if isinstance(exc, Cancelled) else 'stale', str(exc)
            if checkpoint_admitted and outcome in ('complete', 'pending'):
                self.store.db.execute('INSERT OR REPLACE INTO reuse_checkpoints VALUES(?,?)', (signature, packed(st)))
                persisted = True
        return dict(kind=outcome, reason=reason, snapshot=snap.identity, score_contract=SCORE,
            items=st['items'] if outcome == 'complete' else [], state=st if outcome == 'pending' else None,
            checkpoint_persisted=persisted, resources=parent.dump(), cache=self.cache.stats(),
            coverage=dict(accessible=len(accessible), vector_eligible=len(rows), missing_vectors=len(accessible) - len(rows)),
            ann_observed=st.get('ann_observed'), wall_ms=(time.perf_counter() - start) * 1000)

    def restore(self, signature):
        with self.store.lock:
            row = self.store.db.execute('SELECT payload FROM reuse_checkpoints WHERE id=?', (signature,)).fetchone()
        if row is None:
            raise ValueError('unknown checkpoint')
        return json.loads(row[0])
