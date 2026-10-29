"""Necessary checks on fictitious vectors only; no private KB or API."""
from candidate_engine import *
import tempfile


def main():
    passed=[]
    with tempfile.TemporaryDirectory(prefix='candidate-boundaries-') as td:
        store=Store(Path(td)/'fixture.sqlite',2,'fictional')
        store.initialize([dict(id=i+1,vector=v,text=f'虚构资料{i+1}',path='a/x.md' if i<3 else 'b/x.md')
                          for i,v in enumerate([[1.,0.],[.8,.6],[.6,.8],[0.,1.]])],1)
        snap=store.snapshot();q=np.array([.8,.6]);old=np.array([1.,0.])
        e=CandidateEngine(store,snap,'fixture','merge',C=2,candidates=2)
        req=Request(q,k=2,use_cache=False)
        e.seeds.put(e.bucket(req),old,[dict(id=1,version=1),dict(id=2,version=1)],'ann',0,Ledger())
        req.limits={'seed_verifications':1}
        p=e.run(req)
        assert p.kind==ResultKind.PENDING and p.state.prepare_step=='validate'
        assert p.state.request_data['reuse']['cursor']==1
        sig=store.save(p.state,Ledger(consumed=p.state.consumed))
        restored=store.restore(sig)
        fresh=CandidateEngine(store,snap,'fixture','merge',C=2,candidates=2)
        req.limits={'seed_verifications':2,'candidate_cache_lookups':1,'canonical_scores':4}
        r=fresh.run(req,restored)
        assert r.kind==ResultKind.APPROXIMATE
        c=r.resources['consumed']
        assert c['seed_verifications']==2 and c['candidate_cache_lookups']==1 and c['ann_calls']==1
        assert c['canonical_scores']<=4 and len({x['id'] for x in r.items})==2
        passed.append('selected_entry_and_validation_cursor_survive_checkpoint_new_engine')

        req.limits={'canonical_scores':1}
        p=e.run(req)
        assert p.kind==ResultKind.PENDING and p.state.cursor==1
        expected_unique_scores=len(p.state.positions)
        req.limits={'canonical_scores':4,'ann_calls':1,'candidate_cache_lookups':1}
        r=e.run(req,p.state)
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['ann_calls']==1
        assert r.resources['consumed']['canonical_scores']==expected_unique_scores
        passed.append('score_resume_does_not_repeat_ann_match_or_scores')

        empty=CandidateEngine(store,snap,'empty','seed',C=2,candidates=2)
        cap=Request(q,k=2,use_cache=False,limits={'ann_calls':0})
        p=empty.run(cap)
        assert p.kind==ResultKind.PENDING and p.resources['consumed']['candidate_cache_lookups']==1
        cap.limits={'ann_calls':1,'candidate_cache_lookups':1}
        r=empty.run(cap,p.state)
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['ann_calls']==1
        passed.append('empty_cache_fallback_shares_parent_budget_and_terminates')

        bad=e.run(Request(q,k=2,limits={'ann_distance_evaluations':1}))
        assert bad.kind==ResultKind.REJECTED
        passed.append('native_internal_hard_budget_rejected')

        scoped=CandidateEngine(store,snap,'scoped','seed',C=2,candidates=2)
        scoped.seeds=e.seeds
        r=scoped.run(Request(q,k=2,use_cache=False,scope=Scope('b/')))
        assert r.kind==ResultKind.APPROXIMATE and [x['id'] for x in r.items]==[4]
        assert not r.guarantee['reuse']['matched']
        passed.append('scope_bucket_mismatch_cannot_reuse_other_scope')

        cache_req=Request(q,k=2)
        first=e.run(cache_req);hit=e.run(cache_req)
        assert hit.cache_hit and hit.resources['consumed'].get('canonical_scores',0)==0
        assert hit.resources['consumed']['source_reads']==2 and hit.resources['consumed']['state_commits']==1
        passed.append('ordinary_result_cache_keeps_source_and_commit_costs')

        onlyself=CandidateEngine(store,snap,'self','seed',C=2,candidates=2)
        onlyself.seeds.put(onlyself.bucket(req),q,[dict(id=1,version=1)],'ann',0,Ledger())
        r=onlyself.run(Request(q,k=2,use_cache=False))
        assert not r.guarantee['reuse']['matched'] and r.resources['consumed']['ann_calls']==1
        passed.append('own_query_only_bucket_falls_back_instead_of_empty_argmax')

        invalid=CandidateEngine(store,snap,'invalid','seed',C=2,candidates=2)
        invalid.seeds.put(invalid.bucket(req),old,[dict(id=1,version=9),dict(id=99,version=1)],'ann',0,Ledger())
        r=invalid.run(Request(q,k=2,use_cache=False))
        assert r.guarantee['reuse']['stale']==2 and r.resources['consumed']['ann_calls']==1
        passed.append('invalid_versions_and_ids_cannot_be_returned_as_seeds')

        full=CandidateEngine(store,snap,'full','full')
        a=full.run(Request(q,k=2,use_cache=False))
        assert [x['id'] for x in a.items]==[2,3]
        assert a.resources['consumed']['canonical_scores']==4
        passed.append('canonical_reference_and_tie_rule')
        store.mutate('delete',[dict(op='delete',id=2)])
        newer=store.snapshot();ne=CandidateEngine(store,newer,'invalid','seed',C=2,candidates=2)
        ne.seeds=invalid.seeds
        r=ne.run(Request(q,k=2,use_cache=False))
        assert 2 not in [x['id'] for x in r.items] and not r.guarantee['reuse']['matched']
        rejected=e.run(Request(q,k=2,use_cache=False))
        historical=e.run(Request(q,k=2,use_cache=False,snapshot=snap.identity))
        assert rejected.kind==ResultKind.REJECTED and historical.kind==ResultKind.APPROXIMATE
        passed.append('new_snapshot_excludes_deleted_and_old_executor_requires_explicit_snapshot')
        store.close()
    result=dict(passed=len(passed),checks=passed,scope='fictitious mechanics only')
    (Path(__file__).parent/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
