"""Faithful executable versions of WorkBuddy's static P1-P5 call sequences.

Same verdict predicates before/after; only --module changes. Fictitious data.
No real KB, cloud call, benchmark or phase-three action.
"""
import argparse, importlib.util, sys, tempfile, json, hashlib
from pathlib import Path

def run(module):
    spec=importlib.util.spec_from_file_location('probe_framework',module)
    f=importlib.util.module_from_spec(spec); sys.modules[spec.name]=f; spec.loader.exec_module(f)
    findings={}
    with tempfile.TemporaryDirectory(prefix='stage2-review-') as td:
        root=Path(td)
        def make(name):
            s=f.Store(root/(name+'.sqlite'),3,'fixture')
            s.initialize([dict(id=i+1,vector=v,text=t,path=f'{i}.md',
                provenance={'file_sha':'unverified-original'}) for i,(v,t) in enumerate([
                ([1,0,0],'苹果 原文'),([0,1,0],'香蕉 内容'),([0,0,1],'梨子 说明')])],1)
            return s
        store=make('a'); snap=store.snapshot(); engine=f.Engine(store,snap,candidates=3)
        contract=getattr(engine,'hybrid_score',f.HYBRID_SCORE)
        first=f.Request([1,0,0],backend='hybrid',text='苹果',k=2,use_cache=False,
                        score_contract=contract,limits={'lexical_queries':0})
        pending=engine.run(first)
        assert pending.kind==f.ResultKind.PENDING
        ledger=f.Ledger(consumed=pending.state.consumed)
        signature=store.save(pending.state,ledger)
        first.limits={'lexical_queries':1,'metadata_checks':3,'ann_calls':1}
        resumed=engine.run(first,store.restore(signature))
        findings['P1_prepare_resume_duplicates_completed_work']=(resumed.kind!=f.ResultKind.APPROXIMATE)
        evidence={'P1':{'final_kind':resumed.kind.value,'consumed':resumed.resources['consumed']}}

        p=engine.run(f.Request([0,1,0],k=2,use_cache=False,limits={'canonical_scores':1}))
        assert p.kind==f.ResultKind.PENDING
        rejected=False
        try:
            key=store.save(p.state,f.Ledger({'state_commits':1}))
            restored=store.restore(key)
            findings['P2_checkpoint_can_erase_consumed']=(restored.consumed.get('canonical_scores',0)<1)
        except ValueError:
            rejected=True; findings['P2_checkpoint_can_erase_consumed']=False
        evidence['P2']={'fresh_ledger_rejected':rejected}

        store.mutate('text-update',[dict(op='put',id=1,vector=[1,0,0],text='修改后正文',path='0.md',
                         provenance={'file_sha':'unverified-original'})])
        new=store.snapshot(); e=f.Engine(store,new,candidates=3)
        source=e.run(f.Request([1,0,0],k=1,use_cache=False)).items[0]
        verification=source.get('source_verification',{})
        findings['P3_origin_verification_scope_unspecified']=not (
            verification.get('original_file') is False and verification.get('snapshot_content') is True)
        evidence['P3']={'source_verification':verification}

        # Stored chunk digest must detect a text change made outside ingestion.
        columns=[r[1] for r in store.db.execute('PRAGMA table_info(history)')]
        store.db.execute("UPDATE history SET text='unexpected storage edit' WHERE id=1 AND end IS NULL")
        tampered=f.Engine(store,store.snapshot(),candidates=3)
        try:
            bad=tampered.run(f.Request([1,0,0],k=1,use_cache=False))
            findings['P3_stored_text_edit_undetected']=(bad.kind!=f.ResultKind.REJECTED)
        except ValueError:
            findings['P3_stored_text_edit_undetected']=False
        evidence['P3']['persisted_digest_column_present']='content_sha' in columns

        other=make('b')
        try:
            wrong=f.Engine(other,snap,candidates=3)
            result=wrong.run(f.Request([1,0,0],k=1,use_cache=False))
            findings['P4_foreign_snapshot_accepted']=(result.kind!=f.ResultKind.REJECTED)
            wrong.close()
        except ValueError:
            findings['P4_foreign_snapshot_accepted']=False
        # Physical copy with the same instance/revision must still be scoped.
        copy_path=root/'clone.sqlite'
        import sqlite3
        target=sqlite3.connect(copy_path); other.db.backup(target); target.close()
        clone=f.Store(copy_path,3,'fixture')
        findings['P4_copied_store_identity_collides']=(clone.snapshot().identity==other.snapshot().identity)

        hybrid=e.run(f.Request([0,1,0],backend='hybrid',text='香蕉',k=2,
                              score_contract=getattr(e,'hybrid_score',f.HYBRID_SCORE),use_cache=False))
        findings['P5_hybrid_contract_mislabels_pool']=('dense3_lex3' not in hybrid.score_contract)
        evidence['P5']={'contract':hybrid.score_contract}
        for obj in (engine,e,tampered): obj.close()
        for obj in (store,other,clone): obj.close()
    return dict(module_sha256=hashlib.sha256(Path(module).read_bytes()).hexdigest(),
        findings=findings,evidence=evidence,expected_after_fix={k:False for k in findings},
        all_flips_as_expected=not any(findings.values()),
        scope='tiny fictitious SQLite reproductions; no performance or fault-injection claims')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--module',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); result=run(args.module.resolve())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
