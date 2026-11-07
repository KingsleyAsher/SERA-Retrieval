"""Six inherited cases, including terminal round-trip for all four execution paths."""
from scope_engine import *
from contextlib import closing
from types import SimpleNamespace
import tempfile

def main():
    files=[HERE/'scope_engine.py',HERE/'checks.py',HERE.parent/'阶段二/framework.py']
    before={str(p):sha(p.read_bytes()) for p in files};done=[]
    with tempfile.TemporaryDirectory(prefix='scope34-') as td,closing(Store(Path(td)/'test.sqlite',2,'fixture')) as store:
        vv=[[1,0],[.8,.6],[.6,.8],[0,1],[-1,0],[0,-1]]
        paths=['笔记/a','笔记/b','笔记/c','笔记本/a','笔记/hidden','其他/a']
        store.initialize([dict(id=i+1,vector=v,path=paths[i],visible=i!=4,text='虚构',version=1) for i,v in enumerate(vv)],1)
        snap=store.snapshot();directory=DirectoryIndex(snap)
        q=np.array([1.,0.]);scope=Scope('笔记/')
        assignment=np.array([0,0,0,1,1,1],dtype=np.int64)
        geom=SimpleNamespace(snapshot=snap.identity,nlist=2,assignment=assignment,
            centers=np.array([[.8,.4],[-.3,0.]]),lists=[np.array([0,1,2],dtype=np.int64),np.array([3,4,5],dtype=np.int64)])
        def engine(backend='full',row=False,target=6):return ScopeEngine(store,snap,'test-'+backend+str(row),backend,directory,geom if backend=='ivf' else None,target=target,row_scan=row)
        def request(limits=None,k=2,sc=scope):return Request(q,k=k,scope=sc,use_cache=False,limits=limits or {})
        assert directory.resolve('笔记/',Ledger())==[0,1,2]
        assert directory.resolve('笔记本/',Ledger())==[3]
        assert snap.allowed(scope).tolist()==[0,1,2]
        assert engine().run(request(sc=Scope('笔记'))).kind==ResultKind.REJECTED
        done.append('directory_boundary_visibility_and_original_row_scope_agree')
        for backend,row in [('full',True),('full',False),('ivf',False),('ann',False)]:
            e=engine(backend,row);r=e.run(request())
            assert r.kind==ResultKind.APPROXIMATE,(backend,r.reason)
            assert [x['id'] for x in r.items]==[1,2]
            assert r.resources['consumed']['source_reads']==2 and r.resources['consumed']['state_commits']==1
            t=r.resources['seconds'];assert t['other']>=0 and abs(sum(v for k,v in t.items() if k!='total')-t['total'])<1e-12
            signature=store.db.execute('SELECT id FROM executions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
            restored=store.restore(signature);assert restored.phase=='done'
            resumed=engine(backend,row).run(request(),restored)
            assert resumed.items==r.items and resumed.resources['consumed']==r.resources['consumed']
        done.append('four_paths_same_legal_ranking_sources_commit_and_exclusive_timing_sum')
        for backend in ['full','ivf','ann']:
            e=engine(backend)
            empty=e.run(request(k=10,sc=Scope('none/')))
            short=e.run(request(k=10))
            assert empty.kind==short.kind==ResultKind.APPROXIMATE and len(empty.items)==0 and len(short.items)==3
            assert empty.guarantee['eligible']==0 and short.guarantee['termination']=='exhaustive'
        done.append('empty_and_N_less_than_K_are_legal_exhaustive_completions')
        e=engine();caps={'canonical_scores':3,'vector_logical_bytes':16,'state_commits':1}
        p=e.run(request(caps));assert p.kind==ResultKind.PENDING and p.state.cursor==1
        assert p.resources['consumed']['canonical_scores']==1 and p.resources['consumed']['vector_logical_bytes']==16
        e.checkpoint(p.state);restored=store.restore(p.state.signature)
        assert e.run(request(),restored).kind==ResultKind.REJECTED
        r=e.run(request({'canonical_scores':3,'vector_logical_bytes':48,'state_commits':2}),restored,budget_change_reason='fixture caller adds bytes and final commit')
        assert r.kind==ResultKind.APPROXIMATE and r.resources['consumed']['canonical_scores']==3
        assert r.resources['consumed']['vector_logical_bytes']==48 and r.resources['consumed']['state_commits']==2
        done.append('score_byte_admission_checkpoint_parent_cap_and_explicit_addition')
        p=engine('ivf').run(request({'ivf_posting_checks':1}))
        assert p.kind==ResultKind.PENDING
        assert engine('ivf').run(request(sc=Scope('其他/')),p.state).kind==ResultKind.REJECTED
        store.mutate('remove',[dict(op='delete',id=2)])
        assert engine().run(request()).kind==ResultKind.REJECTED
        try:
            ScopeEngine(store,store.snapshot(),'bad','full',directory)
            raise AssertionError('foreign directory accepted')
        except ValueError:pass
        done.append('scope_resume_and_snapshot_dependency_changes_are_rejected')
        pinned=Request(q,k=2,scope=scope,snapshot=snap.identity,use_cache=False,limits={'ann_distance_evaluations':1})
        assert engine('ann').run(pinned).kind==ResultKind.REJECTED
        pinned.limits={};bad=ScopeEngine(store,snap,'too-small','ivf',directory,geom,target=1)
        assert bad.run(pinned).kind==ResultKind.REJECTED
        done.append('unsupported_native_hard_cap_and_impossible_fixed_target_rejected')
    assert before=={str(p):sha(p.read_bytes()) for p in files}
    result=dict(date='2026-10-30',passed=len(done),checks=done,local_dependencies_before_and_after=before,
                scope='fictitious correctness only; no semantic/production quality claim')
    (HERE/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
