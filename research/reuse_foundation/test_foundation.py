"""Public mechanism tests with invented plugin-format assets and bounded work."""
import asyncio
import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from .baselines import Baselines
from .common import Exhausted, Ledger, canonical, digest, packed
from .fixtures import knowledge_fixture, memory_fixture, synthetic_records
from .runtime import (ByteCache, Cancelled, Resources, Stale, atomic_publish,
                      capture_dependencies, validate_dependencies)
from .sources import export_source
from .store import FoundationStore, import_snapshot


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = FoundationStore(self.root / 'foundation.sqlite')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def seed(self, n=128, dimension=8):
        records = list(synthetic_records(n, dimension))
        import_snapshot(records, self.store)
        return records

    def event(self, action, ident='0', **kw):
        return dict(event_id=f'{action}:{ident}:{digest(packed(kw))}', namespace='synthetic', id=ident, action=action, **kw)


class AdapterTests(Case):
    def test_native_kb_utf16_f32_import_and_read_only(self):
        path = knowledge_fixture(self.root / 'kb')
        before = {f.name: f.read_bytes() for f in path.iterdir()}
        exported = export_source('knowledge', path)
        r = exported['records'][0]
        self.assertIn('😀', r['text'])
        report = import_snapshot(exported, self.store)
        self.assertFalse(report['idempotent'])
        self.assertTrue(import_snapshot(exported, self.store)['idempotent'])
        row = self.store.snapshot().rows[0]
        self.assertEqual(row['conversion'], 'fp32_to_normalized_f64_v1')
        self.assertEqual(row['original_vector_sha'], r['provenance']['raw_vector_sha'])
        self.assertAlmostEqual(np.linalg.norm(self.store.vector(row, Ledger())), 1, places=14)
        self.assertEqual(before, {f.name: f.read_bytes() for f in path.iterdir()})

    def test_missing_vectors_remain_explicit(self):
        path = knowledge_fixture(self.root / 'kb')
        m = json.loads((path / 'manifest.json').read_text())
        m['vectors'] = {}
        (path / 'manifest.json').write_text(packed(m))
        report = import_snapshot(export_source('knowledge', path), self.store)
        self.assertEqual(report['missing_vectors'], 1)
        result = Baselines(self.store).run([1, 0, 0, 0])
        self.assertEqual(result['coverage']['missing_vectors'], 1)
        self.assertEqual(result['items'], [])

    def test_kb_checksum_ranges_and_source_map_fail_closed(self):
        for mutation in ('checksum', 'range', 'text', 'policy', 'duplicate', 'slot'):
            with self.subTest(mutation=mutation):
                path = knowledge_fixture(self.root / mutation)
                name = 'manifest.json' if mutation in ('checksum', 'slot') else 'catalog.json' if mutation in ('range', 'duplicate') else 'source-map.json'
                data = json.loads((path / name).read_text())
                if mutation == 'checksum': data['checksums']['0'] = 'bad'
                if mutation == 'slot': data['vectors'] = {k: -1 for k in data['vectors']}
                if mutation == 'range': data['documents'][0]['chunks'][0]['end'] = 10000
                if mutation == 'duplicate': data['documents'] *= 2
                if mutation == 'text': data['documents']['invented.md']['text'] += '!'
                if mutation == 'policy': del data['documents']['invented.md']['visible']
                (path / name).write_text(packed(data))
                with self.assertRaises((ValueError, KeyError)):
                    export_source('knowledge', path)
        self.assertEqual(self.store.current(), [])

    def test_memory_actual_entry_shape_and_controls(self):
        path = memory_fixture(self.root / 'memory.sqlite')
        before = path.read_bytes()
        out = export_source('memory', path)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual({r['scope'] for r in out['records']}, {'global', 'project:invented'})
        self.assertTrue(all(r['vector'] is None for r in out['records']))
        import_snapshot(out, self.store)
        db = sqlite3.connect(path)
        db.execute('UPDATE controls SET excluded=1 WHERE source_id="s0"')
        db.execute('UPDATE controls SET withdrawn_at=2 WHERE source_id="s1"')
        db.commit(); db.close()
        changed = export_source('memory', path)['records']
        self.assertFalse(changed[0]['visible'])
        self.assertEqual(changed[1]['status'], 'withdrawn')

    def test_foreign_store_and_memory_lifecycle_schema(self):
        path = memory_fixture(self.root / 'memory.sqlite')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'isolated'):
            FoundationStore(path)
        self.assertEqual(before, path.read_bytes())
        db = sqlite3.connect(path)
        db.executescript('''CREATE TABLE memory_claims(id TEXT PRIMARY KEY,valid_to INTEGER);
          CREATE TABLE pending_claim_changes(source_id TEXT,seq INTEGER,target_id TEXT);
          INSERT INTO memory_claims VALUES('c0',NULL),('c1',3);
          INSERT INTO pending_claim_changes VALUES('s2',2,'c0');
          UPDATE plugin_memory_entries SET claim_id='c0',detached=0 WHERE id='m0';
          UPDATE plugin_memory_entries SET claim_id='c1',detached=0 WHERE id='m1';''')
        db.commit(); db.close()
        self.assertEqual([r['status'] for r in export_source('memory', path)['records']], ['pending', 'superseded'])

    def test_import_validation_is_atomic(self):
        r = self.seed(1)[0]
        for mutate in (lambda x: x.update(content_sha='bad'), lambda x: x.update(vector=[0] * 8),
                       lambda x: x.update(vector=[float('nan')] * 8), lambda x: x.update(dimension=7),
                       lambda x: x.pop('status'), lambda x: x.update(vector=[2] * 8)):
            bad = copy.deepcopy(r); mutate(bad)
            with self.assertRaises(ValueError): import_snapshot([bad], self.store)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            import_snapshot([r, r], self.store)
        mixed = copy.deepcopy(r); mixed.update(id='new', model='other')
        with self.assertRaisesRegex(ValueError, 'mixed'):
            import_snapshot([r, mixed], self.store)
        self.assertEqual(len(self.store.current()), 1)

    def test_namespaces_keep_provenance_deduplicate_payload(self):
        r = self.seed(1)[0]
        other = copy.deepcopy(r); other['namespace'] = 'another'
        import_snapshot([r, other], self.store)
        self.assertEqual(len(self.store.current()), 2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM reuse_vectors').fetchone()[0], 1)

    def test_full_import_removal_and_empty_source(self):
        records = self.seed(2)
        import_snapshot(records[:1], self.store)
        self.assertEqual(self.store.current()[1]['status'], 'deleted')
        import_snapshot(dict(format=1, records=[], source_manifest=dict(namespace='synthetic')), self.store)
        self.assertTrue(all(r['status'] == 'deleted' for r in self.store.current()))


class DependencyTests(Case):
    def test_same_length_change_and_unrelated_source(self):
        records = self.seed(2)
        old = self.store.snapshot()
        a = capture_dependencies(self.store, [old.rows[0]])
        b = capture_dependencies(self.store, [old.rows[1]])
        r = records[0]; r.update(text=r['text'].replace('source', 'SOURCE'), version='2')
        r['content_sha'] = digest(r['text'])
        self.store.apply_events([self.event('change', record={**r, 'vector': r['vector'].tolist()})])
        self.assertFalse(validate_dependencies(self.store, a))
        self.assertTrue(validate_dependencies(self.store, b))
        self.assertEqual(old.rows[0]['version'], '1')

    def test_withdraw_history_current_permission_and_aba(self):
        self.seed(1)
        snap = self.store.snapshot()
        stamp = capture_dependencies(self.store, snap.rows)
        self.store.apply_events([self.event('withdraw')])
        self.assertFalse(validate_dependencies(self.store, stamp))
        baseline = Baselines(self.store)
        self.assertFalse(baseline.run([1] + [0] * 7)['items'])
        old = baseline.run([1] + [0] * 7, snapshot=snap.identity, historical=True)
        self.assertEqual(len(old['items']), 1)
        self.store.apply_events([self.event('activate')])
        self.assertFalse(validate_dependencies(self.store, stamp), 'ABA must not revive old tasks')
        self.store.apply_events([self.event('permissions', visible=False, policy_revision='2')])
        self.assertFalse(baseline.run([1] + [0] * 7, snapshot=snap.identity, historical=True)['items'])

    def test_event_conflict_rollback_delete_and_retry(self):
        records = self.seed(2)
        event = self.event('delete')
        one = self.store.apply_events([event])
        self.assertEqual(one.identity, self.store.apply_events([event]).identity)
        with self.assertRaises(ValueError): self.store.apply_events([{**event, 'action': 'withdraw'}])
        epoch = self.store.epoch
        with self.assertRaises(ValueError):
            self.store.apply_events([self.event('withdraw', '1'), self.event('withdraw', 'missing')])
        self.assertEqual(self.store.epoch, epoch)
        self.assertEqual(self.store.current()[1]['status'], 'active')
        import_snapshot(records, self.store)  # Retrying old import cannot resurrect deleted source.
        self.assertEqual(self.store.current()[0]['status'], 'deleted')

    def test_scope_and_store_identity(self):
        self.seed(1)
        row = self.store.current()[0]
        stamp = capture_dependencies(self.store, [row])
        other = FoundationStore(self.root / 'other.sqlite')
        try: self.assertFalse(validate_dependencies(other, stamp))
        finally: other.close()
        with self.assertRaises(Stale): capture_dependencies(self.store, [row], scopes=('another',))
        self.store.apply_events([self.event('permissions', visible=True, policy_revision='2', scope='another')])
        self.assertFalse(validate_dependencies(self.store, stamp))

    def test_maintenance_budget_failure_rolls_back(self):
        self.seed(2)
        epoch = self.store.epoch
        parent = Ledger({'maintenance_record_bytes': 0})
        with self.assertRaises(Exhausted):
            self.store.apply_events([self.event('withdraw')], parent)
        self.assertEqual(self.store.epoch, epoch)
        self.assertTrue(all(r['status'] == 'active' for r in self.store.current()))
        self.assertEqual(parent.consumed['maintenance_events'], 1, 'issued work is not refunded')


class BaselineTests(Case):
    def test_window_full_and_direct_reference_128_2048(self):
        for n in (128, 2048):
            records = self.seed(n, 16)
            query = records[0]['vector']
            direct = canonical(np.stack([r['vector'] for r in records]), query)
            expected = sorted([(float(score), int(digest(packed(['synthetic', str(i)]))[:15], 16))
                               for i, score in enumerate(direct)], key=lambda x: (-x[0], x[1]))[:10]
            baseline = Baselines(self.store, cache_bytes=64)
            for window in (1, 31, 256, n):
                result = baseline.run(query, window=window)
                self.assertEqual(result['kind'], 'complete')
                self.assertEqual([(r['score'], r['id']) for r in result['items']], expected)
                self.assertEqual(result['resources']['consumed']['canonical_scores'], n)
                self.assertEqual(result['resources']['consumed']['vector_logical_bytes'], n * 16 * 8)
                self.assertLessEqual(result['cache']['payload_key_bytes'], 64)

    def test_ties_short_k_empty_and_scope(self):
        records = list(synthetic_records(5, 4))
        for r in records: r['vector'] = [1, 0, 0, 0]
        records[0]['scope'] = 'another'
        records[1]['visible'] = False
        records[2]['status'] = 'pending'
        import_snapshot(records, self.store)
        b = Baselines(self.store)
        out = b.run([1, 0, 0, 0], k=10)
        self.assertEqual(len(out['items']), 2)
        self.assertEqual([i['id'] for i in out['items']], sorted(i['id'] for i in out['items']))
        self.assertEqual(b.run([1, 0, 0, 0], scopes=('missing',))['items'], [])

    def test_budget_resume_restart_and_tamper(self):
        records = self.seed(128)
        b = Baselines(self.store)
        pending = b.run(records[0]['vector'], limits={'canonical_scores': 7}, window=4)
        self.assertEqual(pending['kind'], 'pending')
        self.assertEqual(pending['state']['cursor'], 7)
        state = b.restore(pending['state']['signature'])
        done = Baselines(self.store).run(records[0]['vector'], state=state, limits={'canonical_scores': 128}, window=4)
        self.assertEqual(done['kind'], 'complete')
        self.assertEqual(done['resources']['consumed']['canonical_scores'], 128)
        self.assertEqual(done['resources']['consumed']['vector_logical_bytes'], 128 * 8 * 8)
        self.assertEqual(done['items'], b.run(records[0]['vector'], window=4)['items'])
        state['cursor'] += 1
        with self.assertRaises(ValueError): b.run(records[0]['vector'], state=state, window=4)

    def test_source_budget_resume_and_parent_ledger(self):
        records = self.seed(16)
        ledger = Ledger({'source_reads': 1})
        b = Baselines(self.store)
        pending = b.run(records[0]['vector'], ledger=ledger)
        self.assertEqual(pending['kind'], 'pending')
        self.assertEqual(pending['state']['source_cursor'], 1)
        ledger.limits['source_reads'] = 10
        done = b.run(records[0]['vector'], state=pending['state'], ledger=ledger)
        self.assertEqual(done['kind'], 'complete')
        self.assertEqual(ledger.consumed['canonical_scores'], 16)
        self.assertEqual(ledger.consumed['source_reads'], 10)

    def test_parent_ledger_spans_import_maintenance_query(self):
        records = list(synthetic_records(2, 4))
        parent = Ledger({'import_vector_bytes': 64, 'maintenance_events': 1, 'canonical_scores': 1})
        import_snapshot(records, self.store, parent)
        self.store.apply_events([self.event('withdraw', '1')], parent)
        result = Baselines(self.store).run(records[0]['vector'], ledger=parent)
        self.assertEqual(result['kind'], 'complete')
        self.assertEqual(parent.consumed['canonical_scores'], 1)
        self.assertEqual(parent.consumed['maintenance_events'], 1)
        self.assertEqual(parent.consumed['import_vector_bytes'], 64)

    def test_ann_canonical_rerank_and_unsupported_hard_counter(self):
        records = self.seed(128)
        b = Baselines(self.store)
        exact = b.run(records[0]['vector'])
        ann = b.run(records[0]['vector'], backend='ann')
        self.assertEqual(ann['kind'], 'complete')
        self.assertGreaterEqual(len({r['id'] for r in exact['items']} & {r['id'] for r in ann['items']}), 8)
        by_id = {int(digest(packed(['synthetic', r['id']]))[:15], 16): r['vector'] for r in records}
        for item in ann['items']:
            score = canonical(np.array([by_id[item['id']]]), records[0]['vector'])[0]
            self.assertEqual(item['score'], score)
        with self.assertRaises(ValueError): b.run(records[0]['vector'], backend='ann', limits={'ann_visited_members': 1})
        self.assertIn('computed_distances', ann['ann_observed'])

    def test_cancel_stale_and_pre_admission(self):
        records = self.seed(8)
        stop = threading.Event(); stop.set()
        b = Baselines(self.store)
        result = b.run(records[0]['vector'], cancel=stop)
        self.assertEqual(result['kind'], 'cancelled')
        self.assertFalse(result['checkpoint_persisted'])
        pending = b.run(records[0]['vector'], limits={'vector_logical_bytes': 0})
        self.assertEqual(pending['kind'], 'pending')
        self.assertNotIn('canonical_scores', pending['resources']['consumed'])
        old = self.store.snapshot()
        self.store.apply_events([self.event('withdraw')])
        with self.assertRaises(Stale): b.run(records[0]['vector'], snapshot=old.identity)


class PublicationTests(Case):
    def test_sync_replace_guard_cancel_failures_preserve_previous(self):
        target = self.root / 'active.json'
        atomic_publish(target, {'generation': 1})
        def fail(*args): raise OSError('injected failure')
        for kw, error in [({'sync': fail}, OSError), ({'replace': fail}, OSError),
                          ({'guard': lambda: False}, Stale)]:
            with self.assertRaises(error): atomic_publish(target, {'generation': 2}, **kw)
            self.assertEqual(json.loads(target.read_text()), {'generation': 1})
            self.assertEqual(list(self.root.glob('active.json.tmp-*')), [])
        stop = threading.Event(); stop.set()
        with self.assertRaises(Cancelled): atomic_publish(target, {}, cancel=stop)

    def test_byte_cache_exact_budget_and_immutable_values(self):
        c = ByteCache(6)
        self.assertTrue(c.put('a', b'123'))
        self.assertTrue(c.put('b', b'12'))
        self.assertIsNone(c.get('a'))
        self.assertFalse(c.put('huge', b'1234'))
        with self.assertRaises(TypeError): c.put('x', bytearray(b'1'))
        self.assertLessEqual(c.used, 6)

    def test_cli_export_import_query_and_committed_resume(self):
        path = knowledge_fixture(self.root / 'kb')
        exported, target = self.root / 'export.json', self.root / 'cli.sqlite'
        root = Path(__file__).resolve().parents[2]
        def cli(*args):
            run = subprocess.run([sys.executable, '-m', 'research.reuse_foundation', *map(str, args)],
                                 cwd=root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)
        cli('export', '--kind', 'knowledge', '--source', path, '--output', exported)
        cli('import', '--input', exported, '--store', target)
        qfile, result = self.root / 'q.json', self.root / 'result.json'
        qfile.write_text('[1,0,0,0]')
        cli('query', '--store', target, '--vector', qfile, '--output', result, '--limits', '{"canonical_scores":0}')
        pending = json.loads(result.read_text())
        self.assertEqual(pending['kind'], 'pending')
        signature = pending['state']['signature']
        cli('query', '--store', target, '--vector', qfile, '--output', result, '--resume', signature)
        self.assertEqual(json.loads(result.read_text())['kind'], 'complete')


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = FoundationStore(Path(self.temp.name) / 'db.sqlite')
        import_snapshot(list(synthetic_records(2, 4)), self.store)
        self.resources = Resources(self.store)
        self.stamp = capture_dependencies(self.store, self.store.current())

    async def asyncTearDown(self):
        self.store.close(); self.temp.cleanup()

    async def test_coalescing_and_waiter_cancellation(self):
        started, release = asyncio.Event(), asyncio.Event()
        count = 0
        async def work():
            nonlocal count
            count += 1; started.set(); await release.wait(); return b'computed'
        parent = Ledger()
        a = asyncio.create_task(self.resources.run_shared('x', self.stamp, work, parent))
        await started.wait()
        b = asyncio.create_task(self.resources.run_shared('x', self.stamp, work, parent))
        await asyncio.sleep(0)
        a.cancel()
        with self.assertRaises(asyncio.CancelledError): await a
        release.set()
        self.assertEqual(await b, b'computed')
        self.assertEqual(count, 1)
        self.assertEqual(parent.consumed['cache_fills'], 1)
        self.assertEqual(await self.resources.run_shared('x', self.stamp, work, parent), b'computed')

    async def test_invalidated_work_never_refills_cache(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def work(): started.set(); await release.wait(); return b'stale'
        task = asyncio.create_task(self.resources.run_shared('x', self.stamp, work, Ledger()))
        await started.wait()
        self.store.apply_events([dict(event_id='withdraw', namespace='synthetic', id='0', action='withdraw')])
        release.set()
        with self.assertRaises(Stale): await task
        self.assertEqual(self.resources.cache.stats()['entries'], 0)

    async def test_last_cancel_blocks_even_cancellation_suppressed_producer(self):
        started, finished = asyncio.Event(), asyncio.Event()
        async def work():
            started.set()
            try: await asyncio.Event().wait()
            except asyncio.CancelledError: pass
            finally: finished.set()
            return b'must not publish'
        task = asyncio.create_task(self.resources.run_shared('cancel', self.stamp, work, Ledger()))
        await started.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        await finished.wait(); await asyncio.sleep(0)
        self.assertEqual(self.resources.cache.stats()['entries'], 0)

    async def test_background_serializes_yields_and_queue_cancels(self):
        entered, finish, checkpoint = asyncio.Event(), asyncio.Event(), asyncio.Event()
        order = []
        async def foreground(): entered.set(); await finish.wait()
        fg = asyncio.create_task(self.resources.foreground(foreground))
        await entered.wait()
        async def background(yield_now):
            order.append('start'); await yield_now(); order.append('done')
        first = asyncio.create_task(self.resources.background(background))
        cancelled = asyncio.create_task(self.resources.background(background))
        await asyncio.sleep(0); self.assertEqual(order, [])
        cancelled.cancel()
        with self.assertRaises(asyncio.CancelledError): await cancelled
        finish.set(); await fg; await first
        self.assertEqual(order, ['start', 'done'])
        # A foreground arriving while background is active blocks its next checkpoint.
        pause, proceed = asyncio.Event(), asyncio.Event()
        async def active(yield_now):
            pause.set(); await proceed.wait(); await yield_now(); checkpoint.set()
        bg = asyncio.create_task(self.resources.background(active)); await pause.wait()
        entered.clear(); finish.clear()
        fg = asyncio.create_task(self.resources.foreground(foreground)); await entered.wait()
        proceed.set(); await asyncio.sleep(0); self.assertFalse(checkpoint.is_set())
        finish.set(); await fg; await bg
        self.assertTrue(checkpoint.is_set())


if __name__ == '__main__':
    unittest.main()
