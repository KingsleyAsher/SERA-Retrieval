"""Independent executor; opening/enumerating a posting never completes its work."""
import json
import time
from dataclasses import asdict

import numpy as np

from research.reuse_foundation.common import Ledger, Exhausted, canonical, digest, packed, framework

COUNTERS = {'canonical_scores', 'vector_logical_bytes', 'seed_scores', 'new_scan_scores',
            'metadata_checks', 'seed_verifications', 'seed_metadata_bytes', 'coarse_scores',
            'coarse_vector_bytes', 'ivf_lists_opened', 'ivf_posting_checks', 'ivf_posting_bytes',
            'source_reads', 'source_logical_bytes', 'materialized_text_checks', 'state_commits'}


class FrontierEngine:
    def __init__(self, store, snapshot, lists, centers):
        if snapshot.owner != store.namespace:
            raise ValueError('foreign snapshot')
        self.store, self.snap = store, snapshot
        self.lists = tuple(tuple(map(int, values)) for values in lists)
        self.centers = np.asarray(centers, dtype=np.float64).copy()
        self.centers.flags.writeable = False
        flat = [p for values in self.lists for p in values]
        if sorted(flat) != list(range(len(snapshot.ids))) or self.centers.shape != (len(lists), store.dim) or not np.isfinite(self.centers).all():
            raise ValueError('partition must cover each snapshot member exactly once')
        self.fingerprint = digest(packed([snapshot.identity, self.lists, self.centers.tolist()]))
        self.store.db.execute('CREATE TABLE IF NOT EXISTS stage33_states(signature TEXT PRIMARY KEY,payload TEXT)')

    def restore(self, signature):
        row = self.store.db.execute('SELECT payload FROM stage33_states WHERE signature=?', (signature,)).fetchone()
        if not row:
            raise ValueError('missing committed state')
        return json.loads(row[0])

    def coverage(self, state):
        scored = {int(p) for p, _ in state['scored']}
        allowed = set(state['allowed'])
        return {j: [p for p in members if p in allowed and p not in scored]
                for j, members in enumerate(self.lists) if j not in state['completed_partitions']}

    def run(self, request, *, seeds=(), scan_budget=None, state=None):
        started = time.perf_counter()
        q = framework.valid_vector(request.vector, self.store.dim)
        if request.k < 1 or request.quality != 'empirical' or request.score_contract != framework.SCORE:
            raise ValueError('unsupported query contract')
        if request.snapshot is not None and request.snapshot != self.snap.identity:
            raise ValueError('snapshot mismatch')
        if request.snapshot is None and self.store.latest() != self.snap.revision:
            raise ValueError('stale executor')
        if request.scope.updated_on_or_before:
            import datetime
            datetime.date.fromisoformat(request.scope.updated_on_or_before)
        if scan_budget is not None and (type(scan_budget) is not int or scan_budget < 0):
            raise ValueError('invalid fixed scan budget')
        limits = dict(request.limits)
        if any(key not in COUNTERS or type(n) is not int or n < 0 for key, n in limits.items()):
            raise ValueError('unsupported hard counter')
        seed_list = [[int(i), int(v)] for i, v in seeds]
        signature = digest(packed([self.fingerprint, digest(q.tobytes()), asdict(request.scope),
                                   request.k, scan_budget, seed_list, framework.SCORE]))
        if state:
            if state['signature'] != signature or state['owner'] != self.store.namespace or self.restore(signature) != state:
                raise ValueError('checkpoint identity/dependencies/payload mismatch')
            if any(state['consumed'].get(key, 0) > n for key, n in limits.items()):
                raise ValueError('resume below consumed budget')
            s = json.loads(packed(state))
        else:
            s = dict(signature=signature, owner=self.store.namespace, phase='prepare', allowed=[],
                     seed_positions=[], seed_cursor=0, scored=[], order_frontier=[], active_partition=None,
                     enumeration_cursor=0, pending_positions=[], score_cursor=0,
                     completed_partitions=[], source_cursor=0, items=[], consumed={})
        ledger = Ledger(limits, s['consumed'])
        can_commit = False
        outcome, reason = 'approximate', ''

        def score(p, seed=False):
            classification = 'seed_scores' if seed else 'new_scan_scores'
            ledger.charge(canonical_scores=1, vector_logical_bytes=self.store.dim * 8, **{classification: 1})
            value = float(canonical(self.snap.vectors[[p]], q)[0])
            s['scored'].append([p, value])

        def guard():
            if request.deadline_ms is not None and (time.perf_counter() - started) * 1000 >= request.deadline_ms:
                raise Exhausted('soft deadline')

        try:
            ledger.charge(state_commits=1)
            can_commit = True
            if s['phase'] == 'prepare':
                ledger.charge(metadata_checks=len(self.snap.rows), seed_verifications=len(seed_list), seed_metadata_bytes=len(seed_list)*16)
                s['allowed'] = self.snap.allowed(request.scope).tolist()
                allowed = set(s['allowed'])
                id_map = {int(i): p for p, i in enumerate(self.snap.ids)}
                seen = set()
                for ident, version in seed_list:
                    p = id_map.get(ident)
                    if p in allowed and self.snap.rows[p]['version'] == version and p not in seen:
                        seen.add(p); s['seed_positions'].append(p)
                target = min(len(allowed), scan_budget) if scan_budget is not None else len(allowed)
                if target < min(request.k, len(allowed)) or len(s['seed_positions']) > target:
                    raise ValueError('fixed budget cannot cover K or paid seed pool')
                s['target'] = target
                s['phase'] = 'seeds'
            while s['phase'] == 'seeds' and s['seed_cursor'] < len(s['seed_positions']):
                guard()
                score(s['seed_positions'][s['seed_cursor']], True)
                s['seed_cursor'] += 1
            if s['phase'] == 'seeds':
                ledger.charge(coarse_scores=len(self.lists), coarse_vector_bytes=self.centers.nbytes)
                priorities = canonical(self.centers, q)
                for j, members in enumerate(self.lists):
                    for p, value in s['scored']:
                        if p in members: priorities[j] = max(priorities[j], value)
                s['order_frontier'] = sorted(range(len(self.lists)), key=lambda j: (-float(priorities[j]), j))
                s['phase'] = 'frontier'
            while s['phase'] == 'frontier' and len(s['scored']) < s['target']:
                guard()
                if s['active_partition'] is None:
                    if not s['order_frontier']:
                        raise ValueError('coverage exhausted before fixed target')
                    ledger.charge(ivf_lists_opened=1)
                    s['active_partition'] = s['order_frontier'].pop(0)
                    s['enumeration_cursor'] = 0
                    s['pending_positions'] = []; s['score_cursor'] = 0
                j = s['active_partition']
                members = self.lists[j]
                while s['score_cursor'] < len(s['pending_positions']) and len(s['scored']) < s['target']:
                    score(s['pending_positions'][s['score_cursor']])
                    s['score_cursor'] += 1
                if len(s['scored']) == s['target']:
                    break
                # Enumeration and scoring have distinct persisted cursors.
                if s['enumeration_cursor'] < len(members):
                    ledger.charge(ivf_posting_checks=1, ivf_posting_bytes=8)
                    p = members[s['enumeration_cursor']]
                    s['enumeration_cursor'] += 1
                    scored = {int(p) for p, _ in s['scored']}
                    if p in s['allowed'] and p not in scored:
                        s['pending_positions'].append(p)
                while s['score_cursor'] < len(s['pending_positions']) and len(s['scored']) < s['target']:
                    p = s['pending_positions'][s['score_cursor']]
                    score(p)
                    s['score_cursor'] += 1
                if s['enumeration_cursor'] == len(members) and s['score_cursor'] == len(s['pending_positions']):
                    s['completed_partitions'].append(j)
                    s['active_partition'] = None
            if s['phase'] == 'frontier':
                # Seed-only partitions can be covered without opening them.
                scored = {int(p) for p, _ in s['scored']}
                for j, members in enumerate(self.lists):
                    if j not in s['completed_partitions'] and all(p not in s['allowed'] or p in scored for p in members):
                        s['completed_partitions'].append(j)
                s['selected'] = sorted(s['scored'], key=lambda item: (-item[1], int(self.snap.ids[item[0]])))[:request.k]
                s['phase'] = 'sources'
            while s['phase'] == 'sources' and s['source_cursor'] < len(s['selected']):
                guard()
                p, value = s['selected'][s['source_cursor']]
                row = self.snap.rows[p]
                ledger.charge(source_reads=1, source_logical_bytes=len(row['text'].encode()), materialized_text_checks=1)
                if not row['visible'] or digest(row['text']) != row['content_sha']:
                    raise ValueError('snapshot source integrity failure')
                s['items'].append(dict(id=int(self.snap.ids[p]), version=row['version'], score=value,
                    text=row['text'], path=row['path'], provenance=row['provenance']))
                s['source_cursor'] += 1
            s['phase'] = 'done'
        except Exhausted as exc:
            outcome, reason = 'pending', str(exc)
        s['consumed'] = ledger.consumed.copy()
        if can_commit:
            self.store.db.execute('INSERT OR REPLACE INTO stage33_states VALUES(?,?)', (signature, packed(s)))
        return dict(kind=outcome, reason=reason, items=s['items'] if outcome == 'approximate' else [],
                    state=s if outcome == 'pending' else None, checkpoint_persisted=can_commit,
                    signature=signature, resources=ledger.dump(), coverage=self.coverage(s),
                    exhaustive=not any(self.coverage(s).values()), fixed_scan_budget=scan_budget,
                    strict_certificate=False, score_contract=framework.SCORE)
