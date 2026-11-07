"""Offline ordinary-f64 bounds; never used to prune the execution frontier."""
import time
from pathlib import Path

import numpy as np

from research.reuse_foundation.common import Ledger, canonical, digest, packed


def build_statistics(vectors, lists, centers, ledger):
    started = time.perf_counter()
    x, centers = np.asarray(vectors, dtype=np.float64), np.asarray(centers, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] % 16 or not np.isfinite(x).all() or not np.isfinite(centers).all():
        raise ValueError('finite coordinates divisible into 16 subspaces required')
    if sorted(int(p) for members in lists for p in members) != list(range(len(x))):
        raise ValueError('incomplete block coverage')
    ledger.charge(stat_vector_bytes=x.nbytes, stat_members=len(x))
    out = []
    for j, members in enumerate(lists):
        block = x[members]
        if not len(block): raise ValueError('empty diagnostic block')
        offsets = block - centers[j]
        radial = np.linalg.norm(offsets.reshape(len(block), 16, -1), axis=2)
        norm2 = np.einsum('ij,ij->i', block, block)
        out.append(dict(center=centers[j].tolist(), rho=float(np.linalg.norm(offsets, axis=1).max()),
            lo=radial.min(axis=0).tolist(), hi=radial.max(axis=0).tolist(),
            beta=float(np.sqrt(norm2).max()), nu_max=float(norm2.max()),
            members=list(map(int, members)), coverage_sha=digest(packed(list(map(int, members))))))
    payload = len(packed(out).encode())
    ledger.charge(stat_payload_bytes=payload)
    return out, dict(seconds=time.perf_counter()-started, payload_bytes=payload)


def observed_bounds(query, stat):
    q, center = np.asarray(query), np.asarray(stat['center'])
    difference = q - center
    radial = np.linalg.norm(difference.reshape(16, -1), axis=1)
    gaps = np.maximum(np.maximum(np.asarray(stat['lo']) - radial, radial - np.asarray(stat['hi'])), 0)
    sphere = max(float(np.linalg.norm(difference))-stat['rho'], 0)**2
    subspace = float(gaps @ gaps)
    norm2 = float(q @ q)
    l2_upper = lambda lower: (norm2 + stat['nu_max'] - lower)/2
    ball = float(q @ center) + float(np.linalg.norm(q))*stat['rho']
    return dict(lb_sphere=sphere, lb_stat=subspace, lb_combined=max(sphere, subspace),
                ball=ball, sphere=l2_upper(sphere), stat=l2_upper(subspace),
                combined=min(ball, l2_upper(max(sphere, subspace))))


def diagnose(vectors, query, old_query, statistics, paid_positions, k=10):
    """Paid current support threshold and oracle live in separate cost ledgers."""
    x, q, old = np.asarray(vectors), np.asarray(query), np.asarray(old_query)
    positions = sorted(set(map(int, paid_positions)))
    if not positions or min(positions) < 0 or max(positions) >= len(x):
        raise ValueError('invalid paid support pool')
    total_started = time.perf_counter()
    online, evaluation = Ledger(), Ledger()
    online.charge(support_scores=len(positions), support_vector_bytes=len(positions)*x.shape[1]*8)
    tick = time.perf_counter()
    support = canonical(x[positions], q)
    threshold = float(np.sort(support)[-k]) if len(support) >= k else None
    support_seconds = time.perf_counter()-tick
    evaluation.charge(oracle_scores=len(x), oracle_vector_bytes=x.nbytes,
                      old_support_scores=len(positions), old_support_vector_bytes=len(positions)*x.shape[1]*8,
                      l2_reference_vectors=len(x), l2_reference_vector_bytes=x.nbytes)
    tick = time.perf_counter()
    old_support = canonical(x[positions], old)
    old_threshold = float(np.sort(old_support)[-k]) if len(positions) >= k else None
    beta_support = float(np.linalg.norm(x[positions], axis=1).max())
    delta = float(np.linalg.norm(q-old))
    truth = canonical(x, q)
    oracle = float(np.sort(truth)[-min(k, len(x))])
    evaluation_seconds = time.perf_counter()-tick
    rows, unique = [], {name: set() for name in ('ball', 'sphere', 'stat', 'combined', 'transfer')}
    categories = dict(sphere_only=0, stat_only=0, both=0, neither=0)
    violations = []
    planning_seconds = 0.
    for j, stat in enumerate(statistics):
        tick = time.perf_counter()
        online.charge(bound_blocks=1, bound_payload_bytes=len(packed(stat).encode()))
        observed = observed_bounds(q, stat)
        planning_seconds += time.perf_counter()-tick
        # Old bound construction is explicitly charged to evaluation, not free online input.
        tick = time.perf_counter()
        evaluation.charge(old_bound_blocks=1, old_bound_payload_bytes=len(packed(stat).encode()))
        previous = observed_bounds(old, stat)
        observed['transfer'] = previous['combined'] + stat['beta']*delta
        members = set(stat['members']); remaining = members-set(positions)
        maximum = float(truth[list(members)].max())
        true_l2 = float(np.sum((x[list(members)]-q)**2, axis=1).min())
        failures = {name: maximum-value for name, value in observed.items()
                    if not name.startswith('lb_') and value < maximum}
        failures.update({name: value-true_l2 for name, value in observed.items()
                         if name.startswith('lb_') and value > true_l2})
        evaluation_seconds += time.perf_counter()-tick
        if failures: violations.append(dict(block=j, raw_gaps=failures))
        separated = {name: threshold is not None and observed[name] < threshold for name in unique}
        a, b = separated['sphere'], separated['stat']
        categories['both' if a and b else 'sphere_only' if a else 'stat_only' if b else 'neither'] += 1
        for name in unique:
            if separated[name]: unique[name].update(remaining)
        rows.append(dict(block=j, size=len(members), unscored=len(remaining), observed=observed,
                         actual_max_ip=maximum, actual_min_l2=true_l2, paid_threshold=threshold,
                         oracle_threshold=oracle, strict_separation=separated,
                         oracle_excludable=len(remaining) if observed['combined'] < oracle else 0,
                         whole_block_excludable=len(members) if separated['combined'] else 0))
    return dict(blocks=rows, categories=categories, raw_coverage_violations=violations,
        paid_threshold=threshold, old_transferred_support_threshold=None if old_threshold is None else old_threshold-beta_support*delta,
        oracle_threshold=oracle, unique_unscored_excludable={name:len(values) for name,values in unique.items()},
        denominator=len(x), planning_seconds=planning_seconds, support_seconds=support_seconds,
        evaluation_seconds=evaluation_seconds, diagnostic_total_seconds=time.perf_counter()-total_started,
        online_constructible_cost=online.dump(), evaluation_cost=evaluation.dump(),
        strict_certificate=False, online_pruning_qualified=False)


def input_availability(root, inputs_root=None):
    root = Path(root)
    base = Path(inputs_root).resolve() if inputs_root else root/'research'
    required = [base/'.private-kb-experiments/plan-v1-stage1/frozen.sqlite',
                base/'.private-kb-experiments/plan-v1-stage1/source-metadata.json',
                base/'.private-kb-experiments/plan-v1-stage1/manifest.json',
                base/'.private-kb-experiments/embedding-cache.sqlite',
                base/'ChatGPT/真实查询复用研究-v0.14/queries.json']
    # Mirror the archived replay's ROOT calculation exactly; no private directory crawl.
    replay = root/'research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/run_experiment.py'
    text = replay.read_text()
    return dict(status='blocked_missing_frozen_inputs' if any(not p.is_file() for p in required) else 'requires_explicit_private_replay',
                missing=[str(p.relative_to(base)) for p in required if not p.is_file()],
                replay_sha256=digest(text.encode()), actual_128_cases_executed=False,
                screening_decision=None, synthetic_is_not_a_replacement=True)
