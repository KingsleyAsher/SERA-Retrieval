import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from research.reuse_foundation.common import Ledger, canonical, framework
from .frontier import FrontierEngine
from .diagnostics import build_statistics, diagnose, observed_bounds, input_availability


class FrontierChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'fixture.sqlite'
        self.store = framework.Store(self.path, 2, 'invented')
        vv = [[v, float(np.sqrt(1-v*v))] for v in (.5, .6, .95)]
        self.store.initialize([dict(id=i, vector=v, text='Invented', path=f'a/{i}') for i,v in enumerate(vv)], 1)
        self.snap = self.store.snapshot()
        self.engine = FrontierEngine(self.store, self.snap, [[0,1,2]], [[.6,.7]])

    def tearDown(self):
        self.store.close(); self.temp.cleanup()

    def req(self, **kw): return framework.Request([1,0], k=1, use_cache=False, **kw)

    def resume(self, result, **kw):
        engine = FrontierEngine(self.store, self.snap, [[0,1,2]], [[.6,.7]])
        return engine.run(self.req(**kw), state=engine.restore(result['signature']))

    def test_01_partial_partition_new_engine_and_store(self):
        seed = [(0,1)]
        p = self.engine.run(self.req(limits={'canonical_scores':2}), seeds=seed)
        self.assertEqual(p['kind'], 'pending'); self.assertEqual(p['state']['active_partition'], 0)
        self.assertIn(2, p['coverage'][0]); self.assertNotIn(0,p['state']['completed_partitions'])
        self.store.close(); self.store=framework.Store(self.path,2,'invented'); self.snap=self.store.snapshot()
        e=FrontierEngine(self.store,self.snap,[[0,1,2]],[[.6,.7]])
        done=e.run(self.req(),seeds=seed,state=e.restore(p['signature']))
        self.assertEqual(done['items'][0]['id'],2)
        self.assertEqual(done['resources']['consumed']['canonical_scores'],3)

    def test_02_enumeration_and_scoring_interruptions(self):
        p=self.engine.run(self.req(limits={'canonical_scores':0,'ivf_posting_checks':1}))
        self.assertEqual(p['state']['pending_positions'],[0])
        q=self.resume(p,limits={'ivf_posting_checks':1})
        self.assertEqual(q['kind'],'pending'); self.assertEqual(len(q['state']['scored']),1)
        done=self.resume(q)
        self.assertEqual(done['items'][0]['id'],2)
        self.assertEqual(done['resources']['consumed']['ivf_posting_checks'],3)

    def test_03_last_enumerated_member_unscored(self):
        p=self.engine.run(self.req(limits={'canonical_scores':2}))
        self.assertEqual(p['state']['enumeration_cursor'],3)
        self.assertEqual(p['state']['score_cursor'],2)
        self.assertEqual(p['state']['completed_partitions'],[])
        self.assertEqual(self.resume(p)['items'][0]['id'],2)

    def test_04_seed_atomic_admission_zero_one_and_bytes(self):
        seeds=[(0,1),(1,1)]
        for limits in ({'seed_scores':0},{'canonical_scores':0},{'vector_logical_bytes':0}):
            p=self.engine.run(self.req(limits=limits),seeds=seeds)
            self.assertEqual(p['state']['scored'],[])
            for key in ('canonical_scores','vector_logical_bytes','seed_scores'):
                self.assertEqual(p['resources']['consumed'].get(key,0),0)
        p=self.engine.run(self.req(limits={'seed_scores':1}),seeds=seeds)
        e=self.engine
        done=e.run(self.req(),seeds=seeds,state=e.restore(p['signature']))
        self.assertEqual(done['resources']['consumed']['seed_scores'],2)
        self.assertEqual(done['resources']['consumed']['vector_logical_bytes'],48)

    def test_05_seed_deduplication_and_classification(self):
        r=self.engine.run(self.req(),seeds=[(0,1),(0,1),(2,0),(9,1)])
        c=r['resources']['consumed']
        self.assertEqual(c['seed_scores'],1)
        self.assertEqual(c['canonical_scores'],c['seed_scores']+c['new_scan_scores'])
        self.assertEqual(c['canonical_scores'],3)

    def test_06_popped_active_partition_remains_covered(self):
        p=self.engine.run(self.req(limits={'ivf_posting_checks':0}))
        self.assertEqual(p['state']['order_frontier'],[])
        self.assertEqual(p['state']['active_partition'],0)
        self.assertEqual(p['coverage'][0],[0,1,2])
        self.assertEqual(self.resume(p)['items'][0]['id'],2)

    def test_07_small_and_empty_scope(self):
        for scope,n in [(framework.Scope('a/0'),1),(framework.Scope('none/'),0)]:
            r=self.engine.run(framework.Request([1,0],k=10,scope=scope,use_cache=False))
            self.assertEqual(r['kind'],'approximate'); self.assertEqual(len(r['items']),n)
            self.assertTrue(r['exhaustive'])

    def test_08_fixed_target_and_pending_are_different(self):
        r=self.engine.run(self.req(),scan_budget=1)
        self.assertEqual(r['kind'],'approximate'); self.assertFalse(r['exhaustive'])
        p=self.engine.run(self.req(limits={'canonical_scores':0}),scan_budget=1)
        self.assertEqual(p['kind'],'pending')
        with self.assertRaises(ValueError): self.engine.run(self.req(),scan_budget=0)
        with self.assertRaises(ValueError): self.engine.run(self.req(limits={'native_visits':1}))

    def test_09_scope_snapshot_and_tamper_rejected(self):
        p=self.engine.run(self.req(limits={'canonical_scores':1}))
        with self.assertRaises(ValueError): self.engine.run(self.req(scope=framework.Scope('a/0')),state=p['state'])
        changed=json.loads(json.dumps(p['state'])); changed['enumeration_cursor']=999
        with self.assertRaises(ValueError): self.engine.run(self.req(),state=changed)
        self.store.mutate('delete',[dict(op='delete',id=0)])
        with self.assertRaises(ValueError): self.engine.run(self.req(),state=p['state'])
        new=FrontierEngine(self.store,self.store.snapshot(),[[0,1]],[[.6,.7]])
        with self.assertRaises(ValueError): new.run(self.req(),state=p['state'])

    def test_10_exhaustive_canonical_sources_and_commit(self):
        r=self.engine.run(self.req())
        self.assertEqual(r['items'][0]['score'],float(canonical(self.snap.vectors,[1,0]).max()))
        self.assertTrue(r['exhaustive']); self.assertTrue(r['checkpoint_persisted'])
        self.assertEqual(r['items'][0]['text'],'Invented')
        self.assertEqual(self.engine.restore(r['signature'])['phase'],'done')
        p=self.engine.run(self.req(limits={'source_reads':0}))
        done=self.resume(p)
        self.assertEqual(done['resources']['consumed']['canonical_scores'],3)
        self.assertEqual(done['resources']['consumed']['source_reads'],1)


class GeometryChecks(unittest.TestCase):
    def test_nonunit_centers_norm_bridge_and_paid_dedup(self):
        rng=np.random.default_rng(20261107)
        x=rng.normal(size=(32,32)); x/=np.linalg.norm(x,axis=1)[:,None]
        lists=[list(range(16)),list(range(16,32))]
        centers=np.array([x[members].mean(axis=0) for members in lists])
        ledger=Ledger(); stats,_=build_statistics(x,lists,centers,ledger)
        r=diagnose(x,x[0],x[1],stats,list(range(10))*2)
        self.assertEqual(sum(r['categories'].values()),2)
        self.assertEqual(r['online_constructible_cost']['consumed']['support_scores'],10)
        self.assertEqual(r['evaluation_cost']['consumed']['oracle_scores'],32)
        self.assertEqual(r['evaluation_cost']['consumed']['l2_reference_vectors'],32)
        self.assertGreaterEqual(r['diagnostic_total_seconds'],r['planning_seconds'])
        self.assertLessEqual(r['unique_unscored_excludable']['combined'],22)
        self.assertFalse(r['strict_certificate'])
        for stat in stats:
            observed=observed_bounds(x[0],stat)
            self.assertEqual(observed['lb_combined'],max(observed['lb_sphere'],observed['lb_stat']))
            self.assertEqual(observed['sphere'],(float(x[0]@x[0])+stat['nu_max']-observed['lb_sphere'])/2)

    def test_raw_violations_are_not_hidden_and_insufficient_support(self):
        x=np.zeros((16,32)); x[:,0]=1
        stat=dict(center=[0.]*32,rho=0.,lo=[0.]*16,hi=[0.]*16,beta=1.,nu_max=0.,members=list(range(16)))
        r=diagnose(x,x[0],x[0],[stat],[0],k=10)
        self.assertIsNone(r['paid_threshold']); self.assertTrue(r['raw_coverage_violations'])
        self.assertEqual(r['unique_unscored_excludable']['combined'],0)


class InputLocationChecks(unittest.TestCase):
    def test_external_asset_root_does_not_require_repository_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(__file__).resolve().parents[2]
            missing=input_availability(root,td)
            self.assertEqual(len(missing['missing']),5)
            for name in missing['missing']:
                path=Path(td)/name; path.parent.mkdir(parents=True,exist_ok=True); path.touch()
            found=input_availability(root,td)
            self.assertEqual(found['missing'],[])
            self.assertFalse(found['actual_128_cases_executed'])
