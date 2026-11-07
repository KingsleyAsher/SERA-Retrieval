"""Isolated-process synthetic measurements; no semantic or speed acceptance claim."""
import json
import platform
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from .baselines import Baselines
from .common import Ledger, digest, packed
from .fixtures import SEED, synthetic_records
from .store import FoundationStore, import_snapshot


def _peak_rss_bytes():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == 'darwin' else value * 1024)
    except ImportError:
        return None


def worker(arm, count, dimension, repeats):
    with tempfile.TemporaryDirectory(prefix='sera-reuse-bench-') as temp:
        import time
        store = FoundationStore(Path(temp) / 'synthetic.sqlite')
        t = time.perf_counter()
        imported = import_snapshot(synthetic_records(count, dimension), store)
        build_ms = (time.perf_counter() - t) * 1000
        baseline = Baselines(store)
        rng = np.random.default_rng(SEED + 1)
        q = rng.normal(size=dimension); q /= np.linalg.norm(q)
        runs = []
        for _ in range(repeats + 1):
            result = baseline.run(q, backend='ann' if arm == 'ann' else 'exact',
                                  window=count if arm == 'full' else 256)
            if result['kind'] != 'complete':
                raise RuntimeError('benchmark incomplete: ' + result['reason'])
            runs.append(dict(wall_ms=result['wall_ms'],
                scores=[(r['id'], r['score']) for r in result['items']],
                fingerprint=digest(packed(result['items'])), consumed=result['resources']['consumed'],
                cache=result['cache'], ann_observed=result['ann_observed']))
        maintenance_start = time.perf_counter()
        parent = Ledger()
        store.apply_events([dict(event_id='synthetic-withdraw', namespace='synthetic', id='0', action='withdraw')], parent)
        maintenance_ms = (time.perf_counter() - maintenance_start) * 1000
        out = dict(arm=arm, records=count, dimension=dimension, seed=SEED,
            import_ms=build_ms, import_snapshot=imported['snapshot'], cold=runs[0], warm=runs[1:],
            warm_median_ms=statistics.median(r['wall_ms'] for r in runs[1:]),
            peak_rss_bytes=_peak_rss_bytes(), maintenance=dict(wall_ms=maintenance_ms, resources=parent.dump()),
            retained_native_indexes=len(baseline.engines),
            snapshot_note='store owner is isolated per process; compare scores and stable IDs, not snapshot identity')
        store.close()
        return out


def run_benchmark(count=20000, dimension=1024, repeats=3):
    if count < 1 or dimension < 1 or repeats < 1:
        raise ValueError('positive benchmark sizes required')
    arms = []
    for arm in ('full', 'window', 'ann'):
        run = subprocess.run([sys.executable, '-m', 'research.reuse_foundation', '_bench-worker',
            '--arm', arm, '--count', str(count), '--dimension', str(dimension), '--repeats', str(repeats)],
            cwd=Path(__file__).resolve().parents[2], check=True, text=True, capture_output=True)
        arms.append(json.loads(run.stdout))
    if arms[0]['cold']['scores'] != arms[1]['cold']['scores'] or any(
            r['scores'] != arms[0]['cold']['scores'] for a in arms[:2] for r in a['warm']):
        raise AssertionError('exact result mismatch; no successful benchmark report produced')
    truth = {i for i, _ in arms[0]['cold']['scores']}
    for arm in arms:
        arm['top_k_overlap'] = len(truth & {i for i, _ in arm['cold']['scores']}) / max(1, len(truth))
        del arm['import_snapshot']
    return dict(format=1, synthetic=True, environment=dict(python=platform.python_version(),
        numpy=np.__version__, platform=platform.platform()), arms=arms,
        limitations=['one fixed invented corpus and repeated query; no semantic labels',
                     'application logical vector bytes, not physical SSD traffic',
                     'cache budget excludes Python objects, snapshots and native indexes',
                     'process peak includes import, build and query; no per-query RSS claim',
                     'wall time is observed, not a hard deadline',
                     'no power-loss, real-host, private-data or cross-store transaction validation'])
