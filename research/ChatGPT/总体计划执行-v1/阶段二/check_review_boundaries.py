"""Positive boundary checks for review fixes, on tiny fictitious records only."""
from framework import *
import tempfile

def main():
    passed=[]
    with tempfile.TemporaryDirectory(prefix='review-boundary-') as td:
        root=Path(td); store=Store(root/'source.sqlite',2,'fixture')
        store.initialize([dict(id=1,vector=[1,0],text='苹果',path='a.md'),
                          dict(id=2,vector=[0,1],text='香蕉',path='b.md')],1)
        snap=store.snapshot(); e=Engine(store,snap,candidates=2)
        req=Request([1,0],backend='hybrid',text='苹果',k=1,use_cache=False,score_contract=e.hybrid_score,
                    limits={'lexical_queries':0})
        p=e.run(req)
        assert p.kind==ResultKind.PENDING and p.state.prepare_step=='lexical'
        sig=store.save(p.state,Ledger(consumed=p.state.consumed))
        e.close()
        fresh=Engine(store,snap,candidates=2)
        req.limits={'lexical_queries':1,'metadata_checks':2,'ann_calls':1,'index_builds':1}
        r=fresh.run(req,store.restore(sig))
        assert r.kind==ResultKind.APPROXIMATE
        assert r.resources['consumed']['ann_calls']==1 and r.resources['consumed']['metadata_checks']==2
        direct=fresh.run(Request([1,0],backend='hybrid',text='苹果',k=1,use_cache=False,score_contract=fresh.hybrid_score))
        assert [x['id'] for x in r.items]==[x['id'] for x in direct.items]
        passed.append('prepare_checkpoint_new_engine_reuses_completed_ann_and_scope')

        base=Request([1,0],k=1)
        fresh.run(base)
        capped=Request([1,0],k=1,limits={'result_cache_hits':0,'cache_lookups':1})
        p=fresh.run(capped)
        assert p.kind==ResultKind.PENDING and p.state.prepare_step=='cache_return'
        capped.limits={'result_cache_hits':1,'cache_lookups':1}
        r=fresh.run(capped,p.state)
        assert r.kind==ResultKind.APPROXIMATE and r.cache_hit
        assert r.resources['consumed']['cache_lookups']==1
        passed.append('cache_hit_admission_resume_does_not_repeat_lookup')

        target=sqlite3.connect(root/'clone.sqlite'); store.db.backup(target); target.close()
        clone=Store(root/'clone.sqlite',2,'fixture')
        try:
            clone.restore(sig)
            raise AssertionError('foreign checkpoint restored')
        except ValueError as exc:
            assert 'another store' in str(exc)
        try:
            clone.save(p.state,Ledger(consumed=p.state.consumed))
            raise AssertionError('foreign checkpoint saved')
        except ValueError as exc:
            assert 'another store' in str(exc)
        passed.append('copied_store_rejects_foreign_checkpoint_save_and_restore')

        bad=fresh.run(Request([1,0],backend='hybrid',text='苹果',k=1,score_contract=HYBRID_SCORE))
        assert bad.kind==ResultKind.REJECTED
        assert r.resources['time_scope']=='this_invocation_only'
        passed.append('custom_pool_rejects_wrong_hybrid_label_and_scopes_accounting')
        fresh.close(); clone.close(); store.close()
    result=dict(passed=len(passed),checks=passed,scope='fictitious boundary checks only')
    (Path(__file__).parent/'独立审阅修复/boundary-checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
