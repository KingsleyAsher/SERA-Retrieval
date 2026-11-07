"""Independent-query profiling with ordinary-cache controls, private outputs only."""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

from research.reuse_foundation.common import framework as f, digest, packed
from research.reuse_foundation.runtime import atomic_publish


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2];inputs=Path(args.inputs_root).resolve();out=Path(args.output).resolve()
    if out.exists() or out.is_relative_to(root):raise ValueError('use a new private output directory outside Git')
    original=root/'research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF'
    sys.path.insert(0,str(original));spec=importlib.util.spec_from_file_location('_audit_inputs',original/'run_experiment.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=inputs;m.PRIVATE=inputs/'.private-kb-experiments'
    records,queries,texts,model,manifest,load=m.load_inputs()
    if manifest['snapshot_revision']!=1216 or len(records)!=1213 or len(queries)!=48 or len(set(texts))!=48:raise ValueError('frozen input mismatch')
    out.mkdir(parents=True);store=f.Store(out/'execution.sqlite',1024,model)
    started=time.perf_counter();store.initialize(records,1216);snap=store.snapshot()
    init=dict(seconds=time.perf_counter()-started,snapshot_bytes=snap.logical_bytes,load=load)
    engines={b:f.Engine(store,snap,candidates=50,ef=128) for b in ('full','ann','hybrid')}
    def request(b,qi,cache=False):
        return f.Request(queries[qi],backend=b,text=texts[qi],k=10,use_cache=cache,
                         score_contract=engines[b].hybrid_score if b=='hybrid' else f.SCORE)
    def brief(result):
        if result.kind!=f.ResultKind.APPROXIMATE:raise RuntimeError(result.reason)
        return dict(ids=[x['id'] for x in result.items],resources=result.resources,cache_hit=result.cache_hit)
    warmup={b:brief(e.run(request(b,0))) for b,e in engines.items()}
    measurements=[];rankings={};packets=[];matching=[]
    for rep in range(3):
        for qi in range(48):
            order=list(engines); shift=(rep+qi)%3;order=order[shift:]+order[:shift]
            for b in order:
                result=engines[b].run(request(b,qi));row=dict(rep=rep,query=qi,backend=b,**brief(result));measurements.append(row)
                rankings.setdefault((b,qi),row['ids'])
                if b=='full' and rep==0 and qi%3==0:
                    packets.append(dict(family=qi//3,queries=texts[qi:qi+3],candidates=[
                        dict(id=x['id'],text=x['text'],path=x['path'],version=x['version'],content_sha=next(r['content_sha'] for r in snap.rows if r['id']==x['id']))
                        for x in result.items[:2]]))
    anchors=np.asarray(queries[::3])
    anchor_hashes=[digest(v.tobytes()) for v in anchors]
    for rep in range(3):
        for qi,q in enumerate(queries):
            tick=time.perf_counter();values=f.canonical(anchors,q)
            query_hash=digest(q.tobytes())
            eligible=[i for i in range(16) if anchor_hashes[i]!=query_hash]
            selected=min(eligible,key=lambda i:(-float(values[i]),i))
            matching.append(dict(rep=rep,query=qi,anchor=selected,seconds=time.perf_counter()-tick,scores=16,logical_bytes=anchors.nbytes))
    cache_pairs=[]
    for b,e in engines.items():
        for qi in range(48):
            miss=e.run(request(b,qi,True));hit=e.run(request(b,qi,True))
            if miss.cache_hit or not hit.cache_hit or [i['id'] for i in miss.items]!=[i['id'] for i in hit.items]:raise AssertionError('controlled cache pair mismatch')
            cache_pairs.append(dict(backend=b,query=qi,miss=brief(miss),hit=brief(hit)))
    source=inputs/'.private-kb-experiments/plan-v1-stage1/frozen.sqlite'
    import sqlite3
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    journal_columns=[r[1] for r in db.execute('PRAGMA table_info(journal)')]
    metadata=json.loads((inputs/'.private-kb-experiments/plan-v1-stage1/source-metadata.json').read_text())
    card=dict(chunks=len(records),sources=len({r['path'] for r in records}),queries=len(texts),authored_families=16,
        natural_query_trace_supplied=False,replayable_update_history_supplied=False,journal_columns=journal_columns,
        journal_rows=db.execute('SELECT count(*) FROM journal').fetchone()[0],
        journal_has_timestamp=any('time' in c for c in journal_columns),
        updated_present_sources=sum(bool(r.get('updated')) for r in metadata),
        stage1_seed_qrels_supplied=False,semantic_gold_available=False,
        corpus_vector_sha=manifest['vector_sha256'],protocol_sha=digest((Path(__file__).parent/'protocol.json').read_bytes()))
    db.close()
    atomic_publish(out/'data-card.json',card);atomic_publish(out/'review-packet.json',dict(grade_scale={'0':'irrelevant','1':'related but incomplete','2':'direct evidence for this wording'},packets=packets))
    atomic_publish(out/'measurements.json',dict(initialization=init,warmup=warmup,measurements=measurements,cache_pairs=cache_pairs,matching=matching,
        code_sha256=digest(Path(__file__).read_bytes()),natural_trace=False,formal_semantic_metrics=None))
    for e in engines.values():e.close()
    store.close();print(packed(dict(measurements=len(measurements),controlled_cache_pairs=len(cache_pairs),review_families=len(packets))))


if __name__=='__main__':main()
