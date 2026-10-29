"""Bounded correctness checks on fictitious vectors/text, never training data."""
from framework import *
import tempfile

def check():
    passed = []
    with tempfile.TemporaryDirectory(prefix='stage2-check-') as td:
        path = Path(td)/'fixture.sqlite'
        store = Store(path, 3, 'fixture-only-not-a-comparison-model')
        records = [dict(id=i+1, vector=v, text=text, path=path, updated=date) for i, (v,text,path,date) in enumerate([
            ([1,0,0], '苹果 项目 正式资料', 'alpha/one.md', '2026-01-01'),
            ([1,0,0], '苹果 项目 第二来源', 'beta/two.md', '2026-02-01'),
            ([0,1,0], '香蕉 方案', 'alpha/three.md', None),
            ([0,0,1], '旧版 梨子', 'beta/four.md', '2026-03-01')])]
        store.initialize(records, 1)
        old = store.snapshot()
        cache = ResultCache()
        engine = Engine(store, old, cache, candidates=4)
        req = Request([1,0,0], k=2)
        full = engine.run(req)
        assert [r['id'] for r in full.items] == [1,2]
        assert full.guarantee['strict_certificate'] is False
        passed.append('canonical_tie_order_and_no_strict_claim')
        hit = engine.run(req)
        assert hit.cache_hit and hit.resources['consumed'].get('canonical_scores',0)==0
        assert hit.resources['consumed']['source_reads']==2
        passed.append('shared_result_cache_still_charges_source_fetch')
        for b in ('ann','hybrid'):
            result = engine.run(Request([1,0,0],backend=b,text='苹果',k=2,
                score_contract=engine.hybrid_score if b=='hybrid' else SCORE))
            assert result.kind == ResultKind.APPROXIMATE and {r['id'] for r in result.items} == {1,2}
        passed.append('ann_and_chinese_hybrid_same_snapshot')
        filtered = engine.run(Request([1,0,0],k=3,scope=Scope('alpha/', '2026-01-31')))
        assert [r['id'] for r in filtered.items] == [1]
        passed.append('source_date_scope_and_unknown_date_exclusion')
        pending_req = Request([0,1,0],k=2,use_cache=False,limits={'canonical_scores':1})
        pending = engine.run(pending_req)
        assert pending.kind == ResultKind.PENDING and pending.resources['consumed']['canonical_scores']==1
        ledger = Ledger(consumed=pending.state.consumed)
        checkpoint = store.save(pending.state, ledger)
        restored = store.restore(checkpoint)
        pending_req.limits = {'canonical_scores':4}
        resumed = engine.run(pending_req, restored)
        direct = engine.run(Request([0,1,0],k=2,use_cache=False))
        assert [r['id'] for r in resumed.items]==[r['id'] for r in direct.items]
        assert resumed.resources['consumed']['canonical_scores']==4
        passed.append('charged_budget_truncation_persist_restore_resume')
        wrong = engine.run(Request([1,0,0],k=2), restored)
        assert wrong.kind == ResultKind.REJECTED
        passed.append('checkpoint_cannot_change_query')
        ops = [dict(op='delete',id=1), dict(op='put',id=2,vector=[0,0,1],text='改写 新版',path='beta/two.md'),
               dict(op='put',id=3,vector=[0,1,0],text='香蕉 隐藏',path='alpha/three.md',visible=False),
               dict(op='put',id=5,vector=[1,0,0],text='苹果 新增',path='alpha/new.md')]
        rev, cost = store.mutate('fixture-update', ops)
        assert rev==2 and store.mutate('fixture-update',ops)[0]==2 and store.latest()==2
        try:
            store.mutate('fixture-update',[dict(op='delete',id=2)])
            raise AssertionError('different operation with same ID accepted')
        except ValueError:
            pass
        passed.append('atomic_batch_and_idempotent_request_digest')
        new = store.snapshot()
        updated = Engine(store, new, cache, candidates=4)
        for backend in ('full','ann','hybrid'):
            result = updated.run(Request([1,0,0],backend=backend,text='苹果',k=3,
                score_contract=updated.hybrid_score if backend=='hybrid' else SCORE))
            ids = [r['id'] for r in result.items]
            assert 1 not in ids and 3 not in ids and 5 in ids and not result.cache_hit
            assert any(r['id']==2 and r['text']=='改写 新版' for r in result.items)
        assert engine.run(req).kind==ResultKind.REJECTED
        req.snapshot=old.identity
        assert [r['id'] for r in engine.run(req).items]==[1,2]
        passed.append('append_modify_delete_visibility_new_epoch_and_pinned_old_epoch')
        assert engine.run(Request([1,0,0],snapshot=new.identity)).kind==ResultKind.REJECTED
        assert engine.run(Request([float('nan'),0,0])).kind==ResultKind.REJECTED
        assert engine.run(Request([1,0,0],quality='strict')).kind==ResultKind.REJECTED
        assert engine.run(Request([1,0,0],backend='ann',limits={'ann_distance_evaluations':1})).kind==ResultKind.REJECTED
        passed.append('invalid_input_snapshot_guarantee_and_native_cap_rejected')
        state_limit = engine.run(Request([0,0,1],snapshot=old.identity,use_cache=False,limits={'state_commits':0}))
        assert state_limit.kind==ResultKind.PENDING and state_limit.state.phase=='commit'
        empty = engine.run(Request([1,0,0],snapshot=old.identity,scope=Scope('nonexistent/')))
        assert empty.items==[]
        passed.append('commit_budget_and_empty_filter')
        ledger = Ledger({'io':1000}, {'io':600})
        ledger.charge(io=300)
        try:
            ledger.charge(io=300)
            raise AssertionError('budget overspent')
        except Exhausted:
            assert ledger.consumed['io']==900
        passed.append('multi_action_budget_no_refund_or_reset')
        identity = new.identity
        engine.close(); updated.close(); store.close()
        reopened = Store(path, 3, 'fixture-only-not-a-comparison-model')
        assert reopened.snapshot().identity==identity
        assert len(reopened.snapshot().rows)==4
        reopened.close()
        passed.append('normal_reopen_revision_catalog_and_sources')
    result = dict(passed=len(passed), checks=passed,
                  scope='fictitious correctness fixtures; no process fault injection or power-loss validation')
    (Path(__file__).parent/'checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    check()
