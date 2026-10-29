"""Small fictitious mechanics checks for stage3.2."""
from execution_engine import *
from layouts import IVF
import tempfile
from contextlib import closing

def main():
    done=[]
    with tempfile.TemporaryDirectory(prefix='ivf-check-') as td, closing(Store(Path(td)/'fixture.sqlite',2,'fixture')) as s:
        vv=[[1,0],[.8,.6],[.6,.8],[0,1],[-1,0],[0,-1]]
        s.initialize([dict(id=i+1,vector=v,text='虚构',path='a/'+str(i)) for i,v in enumerate(vv)],1)
        snap=s.snapshot();ivf=IVF(snap,2);q=np.array([.8,.6]);old=np.array([1.,0.])
        a=CandidateBank('json');b=CandidateBank('compact')
        for bank in (a,b):
            bank.put('bucket',old,[dict(id=1,version=1),dict(id=2,version=1)],'ann',0,Ledger())
        ma=a.match('bucket',q,Ledger());mb=b.match('bucket',q,Ledger())
        assert ma==mb
        done.append('compact_and_json_same_entry_payload_and_selection')
        cold=CandidateEngine(s,snap,'cold','ivf-cold',ivf=ivf,scan_budget=6)
        warm=CandidateEngine(s,snap,'warm','ivf-warm',C=2,ivf=ivf,scan_budget=6)
        req=Request(q,k=2,use_cache=False)
        warm.seeds.put(warm.bucket(req),old,[dict(id=1,version=1),dict(id=2,version=1)],'ann',0,Ledger())
        for e in (cold,warm):
            r=e.run(req);assert r.kind==ResultKind.APPROXIMATE,(r.kind,r.reason)
            truth=snap.ids[np.lexsort((snap.ids,-canonical(snap.vectors,q)))[:2]].tolist()
            assert [x['id'] for x in r.items]==truth and r.resources['consumed']['canonical_scores']==6
        done.append('full_budget_cold_and_warm_equal_canonical_reference_without_duplicate_scores')
        limited=Request(q,k=2,use_cache=False,limits={'canonical_scores':1})
        p=warm.run(limited);assert p.kind==ResultKind.PENDING and p.state.prepare_step=='seed_score'
        sig=s.save(p.state,Ledger(consumed=p.state.consumed))
        new=CandidateEngine(s,snap,'warm','ivf-warm',C=2,ivf=ivf,scan_budget=6)
        limited.limits={'canonical_scores':6,'candidate_cache_lookups':1}
        r=new.run(limited,s.restore(sig))
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['candidate_cache_lookups']==1
        assert r.resources['consumed']['canonical_scores']==6 and r.resources['consumed']['seed_scores']==2
        done.append('seed_scoring_checkpoint_new_engine_keeps_payload_cursor_and_cost')
        reqcap=Request(q,k=2,use_cache=False,limits={'ivf_posting_checks':1})
        p=warm.run(reqcap);assert p.kind==ResultKind.PENDING and p.state.prepare_step=='frontier'
        old_meta=p.resources['consumed']['metadata_checks'];old_coarse=p.resources['consumed']['coarse_scores']
        reqcap.limits={'ivf_posting_checks':12,'candidate_cache_lookups':1,'canonical_scores':6}
        r=warm.run(reqcap,p.state)
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['metadata_checks']==old_meta
        assert r.resources['consumed']['coarse_scores']==old_coarse and r.resources['consumed']['canonical_scores']==6
        done.append('frontier_member_cursor_resume_does_not_repeat_coarse_or_seed_work')
        p=cold.run(Request(q,k=2,use_cache=False,limits={'canonical_scores':2}))
        assert p.kind==ResultKind.PENDING and p.state.cursor==2
        expected=p.resources['consumed']['ivf_posting_checks']
        r=cold.run(Request(q,k=2,use_cache=False,limits={'canonical_scores':6,'ivf_posting_checks':expected}),p.state)
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['canonical_scores']==6
        done.append('canonical_score_resume_does_not_repeat_frontier')
        hitreq=Request(q,k=2);warm.run(hitreq);hit=warm.run(hitreq)
        assert hit.cache_hit and hit.resources['consumed']['source_reads']==2 and hit.resources['consumed']['state_commits']==1
        assert hit.resources['consumed'].get('canonical_scores',0)==0
        done.append('result_cache_hit_keeps_source_and_commit_cost')
        r=warm.run(Request(q,k=2,use_cache=False,scope=Scope('none/')))
        assert r.kind==ResultKind.APPROXIMATE and not r.items and not r.guarantee['reuse']['matched']
        done.append('empty_filter_completes_without_seed_leak')
        e=CandidateEngine(s,snap,'budget','ivf-warm',C=2,ivf=ivf,scan_budget=3)
        r=e.run(req)
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['canonical_scores']==3
        assert not r.guarantee['reuse']['matched']
        done.append('empty_seed_bucket_falls_back_within_same_fixed_vector_budget')
        bad=warm.run(Request(q,k=2,limits={'ann_distance_evaluations':1}))
        assert bad.kind==ResultKind.REJECTED
        done.append('unsupported_hard_internal_budget_rejected')
        s.mutate('delete',[dict(op='delete',id=2)]);ss=s.snapshot()
        try:
            CandidateEngine(s,ss,'foreign','ivf-cold',ivf=ivf,scan_budget=6)
            raise AssertionError('foreign IVF accepted')
        except ValueError:pass
        done.append('IVF_snapshot_binding_prevents_cross_update_reuse')
    result=dict(passed=len(done),checks=done,scope='fictitious mechanics; no certificates')
    (Path(__file__).parent/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
