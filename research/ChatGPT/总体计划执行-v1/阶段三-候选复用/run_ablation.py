"""Fixed finite development replay. No network client or secret configuration."""
from candidate_engine import *
import platform,importlib.metadata

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIVATE=ROOT/'.private-kb-experiments'


def write(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def stats(xs):
    if not xs:return None
    a=np.asarray(xs,dtype=np.float64)
    return dict(n=len(xs),mean=float(a.mean()),minimum=float(a.min()),p10=float(np.percentile(a,10)),
                p50=float(np.percentile(a,50)),p95=float(np.percentile(a,95)),maximum=float(a.max()))


def specs():
    out=[dict(label='ann50-ef128',mode='ann',C=0,count=50,ef=128,origin=None),
         dict(label='full',mode='full',C=0,count=50,ef=128,origin=None)]
    for C in (10,50,200):
        for origin in ('ann','full'):
            for mode in ('seed','merge'):
                out.append(dict(label=f'{mode}-{origin}-C{C}',mode=mode,C=C,count=50,ef=128,origin=origin))
        for ef in (128,512):
            out.append(dict(label=f'fresh{50+C}-ef{ef}',mode='ann',C=C,count=50+C,ef=ef,origin=None))
    return out


def brief(result):
    assert result.kind==ResultKind.APPROXIMATE,(result.kind,result.reason)
    return dict(ids=[x['id'] for x in result.items],resources=result.resources,
                cache_hit=result.cache_hit,guarantee=result.guarantee)


def main():
    protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    base=HERE.parent/'阶段二/framework.py'
    assert sha(base.read_bytes())==protocol['base_framework_sha256']
    parent=PRIVATE/'plan-v1-stage3-candidate';parent.mkdir(exist_ok=True)
    out=next(parent/f'run-{i:03d}' for i in range(1,1000) if not (parent/f'run-{i:03d}').exists())
    out.mkdir();write(out/'protocol.json',protocol)
    t=time.perf_counter();frozen=PRIVATE/'plan-v1-stage1'
    db=sqlite3.connect((frozen/'frozen.sqlite').as_uri()+'?mode=ro',uri=True)
    rows=db.execute('SELECT d.id,d.vector,d.text,d.version,d.visible,c.path,c.start,c.end,c.start_line,c.end_line,c.file_sha '
                    'FROM docs d JOIN chunks c ON d.id=c.id ORDER BY d.id').fetchall();db.close()
    dates={r['path']:r['updated'] for r in json.loads((frozen/'source-metadata.json').read_text(encoding='utf-8'))}
    records=[dict(id=r[0],vector=np.frombuffer(r[1],dtype=np.float64),text=r[2],version=r[3],visible=r[4],
        path=r[5],updated=dates.get(r[5]),provenance=dict(start=r[6],end=r[7],start_line=r[8],end_line=r[9],
            file_sha=r[10],kind='frozen_extracted_chunk')) for r in rows]
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    assert sha(np.stack([r['vector'] for r in records]).tobytes())==manifest['vector_sha256']
    input_seconds=time.perf_counter()-t
    namespace=json.loads((HERE.parent/'stage1_protocol.json').read_text(encoding='utf-8'))['model']
    groups=json.loads((ROOT/'ChatGPT/真实查询复用研究-v0.14/queries.json').read_text(encoding='utf-8'))
    assert len(groups)==16 and all(len(g)==3 for g in groups)
    texts=[x for g in groups for x in g]
    t=time.perf_counter();db=sqlite3.connect((PRIVATE/'embedding-cache.sqlite').as_uri()+'?mode=ro',uri=True)
    vectors=[]
    for text in texts:
        r=db.execute('SELECT vector FROM vectors WHERE namespace=? AND sha=?',(namespace,sha(text.encode()))).fetchone()
        if r is None:raise RuntimeError('missing cached BGE vector; API fallback disabled')
        vectors.append(np.frombuffer(r[0],dtype=np.float64).copy())
    db.close();embedding_seconds=time.perf_counter()-t
    store=Store(out/'execution.sqlite',1024,namespace)
    import_seconds=store.initialize(records,1216);snap=store.snapshot()
    truth=[];topc={}
    for qi,q in enumerate(vectors):
        scores=canonical(snap.vectors,q);order=np.lexsort((snap.ids,-scores))
        truth.append(snap.ids[order[:10]].tolist())
        if qi%3==0:
            for C in (10,50,200):topc[(qi,C)]=set(snap.ids[order[:C]].tolist())
    main_rows=[];warm_rows=[];fill_rows=[];construct=[];cache_write=[]
    configurations=specs();trace=[]
    for family in range(16):
        for variant,repeat in [(0,False),(1,False),(1,True),(2,False),(2,True)]:
            trace.append(dict(query=family*3+variant,family=family,variant=variant,repeat=repeat))
    for rep in range(3):
        engines={}
        for s in configurations:
            t=time.perf_counter()
            e=CandidateEngine(store,snap,s['label'],s['mode'],s['C'],s['count'],s['ef'])
            engines[s['label']]=e
            construct.append(dict(rep=rep,arm=s['label'],seconds=time.perf_counter()-t,
                                  position_map_entries=len(e.id_positions)))
        # All arms receive identical anchor sequence; result K10 warmup is separate from seed fill.
        for family in range(16):
            qi=family*3
            for s in configurations:
                e=engines[s['label']]
                r=e.run(Request(vectors[qi],text=texts[qi]),prewarm=True)
                warm_rows.append(dict(rep=rep,arm=s['label'],query=qi,**brief(r)))
        for s in configurations:
            if not s['origin']:continue
            e=engines[s['label']]
            filler=Engine(store,snap,cache=ResultCache(),candidates=s['C'],ef=128)
            filler.ann=e.ann  # same ef128 index and layout, not rebuilt for each C fill
            for family in range(16):
                qi=family*3
                req=Request(vectors[qi],backend=s['origin'],k=s['C'],text=texts[qi],use_cache=False)
                r=filler.run(req);b=brief(r)
                l=Ledger();t=time.perf_counter()
                key=e.seeds.put(e.bucket(Request(vectors[qi])),vectors[qi],r.items,s['origin'],family,l)
                l.elapsed('candidate_write',t)
                l.elapsed('total',t)
                cache_write.append(dict(rep=rep,arm=s['label'],entry=key,resources=l.dump()))
                fill_rows.append(dict(rep=rep,arm=s['label'],query=qi,
                    old_topC_overlap=len(set(b['ids'])&topc[(qi,s['C'])])/s['C'],**b))
            filler.close()
        print(f'prewarm_and_fill_complete rep={rep+1} arms={len(configurations)}',flush=True)
        for ti,event in enumerate(trace):
            shift=(ti+rep)%len(configurations)
            order=configurations[shift:]+configurations[:shift]
            for s in order:
                qi=event['query'];e=engines[s['label']]
                limit=len(snap.ids) if s['mode']=='full' else 50+s['C']
                r=e.run(Request(vectors[qi],text=texts[qi],limits={'canonical_scores':limit}))
                row=dict(rep=rep,trace_index=ti,arm=s['label'],**event,**brief(r))
                ids=row['ids'];row['overlap']=len(set(ids)&set(truth[qi]))/10
                assert len(ids)==len(set(ids))==10
                assert r.resources['consumed'].get('canonical_scores',0)<=limit
                assert r.resources['consumed']['source_reads']==10
                if s['mode']=='full':assert ids==truth[qi]
                reuse=r.guarantee['reuse'];origin= reuse.get('origin_sequence')
                if origin is not None:
                    fill=next(x for x in fill_rows if x['rep']==rep and x['arm']==s['label'] and x['query']==origin*3)
                    row['new_query_seed_top10_coverage']=len(set(fill['ids'])&set(truth[qi]))/10
                    row['matched_same_family']=origin==event['family']
                main_rows.append(row)
        write(out/'progress.json',dict(completed_repetitions=rep+1,main_requests=len(main_rows),stage='fixed replay'))
        print(f'main_complete rep={rep+1} requests={len(main_rows)}',flush=True)
        for e in engines.values():e.close()
    all_resource_keys=sorted({k for x in main_rows+warm_rows+fill_rows+cache_write for k in x['resources']['consumed']})
    aggregates=[]
    for s in configurations:
        label=s['label'];rows=[x for x in main_rows if x['arm']==label]
        rewrites=[x for x in rows if x['variant']>0 and not x['repeat']]
        misses=[x for x in rows if not x['cache_hit']]
        warm=[x for x in warm_rows if x['arm']==label]
        fill=[x for x in fill_rows if x['arm']==label]
        writes=[x for x in cache_write if x['arm']==label]
        lifecycle=rows+warm+fill+writes
        def timing(rs,key='total'):
            return stats([x['resources']['seconds'].get(key,0)*1000 for x in rs])
        resources={k:stats([x['resources']['consumed'].get(k,0) for x in rewrites]) for k in all_resource_keys}
        aggregate=dict(**s,requests=len(rows),rewrites=len(rewrites),
            foreground_ms=timing(rows),rewrite_ms=timing(rewrites),miss_ms=timing(misses),
            rewrite_overlap=stats([x['overlap'] for x in rewrites]),
            rewrite_failures=sum(x['overlap']<.9 for x in rewrites),
            component_ms={k:timing(rewrites,k) for k in ['prepare','candidate_match','seed_validation','ann_search','canonical_score','rank','source_fetch','state_commit']},
            resources=resources,result_cache_hits=sum(x['cache_hit'] for x in rows),
            candidate_match_requests=sum(x['guarantee']['reuse'].get('matched',False) for x in rows),
            matched_same_family=stats([float(x['matched_same_family']) for x in rewrites if 'matched_same_family' in x]),
            seed_new_query_coverage=stats([x['new_query_seed_top10_coverage'] for x in rewrites if 'new_query_seed_top10_coverage' in x]),
            fill_old_topC_overlap=stats([x['old_topC_overlap'] for x in fill]),
            per_rep=[dict(rep=rep,rewrite_mean_ms=float(np.mean([x['resources']['seconds']['total']*1000 for x in rewrites if x['rep']==rep])),
                overlap_mean=float(np.mean([x['overlap'] for x in rewrites if x['rep']==rep]))) for rep in range(3)],
            prewarm_ms=sum(x['resources']['seconds']['total']*1000 for x in warm),
            candidate_fill_ms=sum(x['resources']['seconds']['total']*1000 for x in fill),
            candidate_write_ms=sum(x['resources']['seconds']['total']*1000 for x in writes),
            lifecycle_ms=sum(x['resources']['seconds']['total']*1000 for x in lifecycle)+
                sum(x['seconds']*1000 for x in construct if x['arm']==label),
            lifecycle_consumed={k:sum(x['resources']['consumed'].get(k,0) for x in lifecycle) for k in all_resource_keys},
            peak_candidate_payload_bytes=max(x['guarantee']['candidate_cache_payload_bytes'] for x in rows),
            peak_result_payload_bytes=max(x['guarantee']['result_cache_payload_bytes'] for x in rows),
            peak_ann_resident_bytes=max(x['guarantee']['index_resident_bytes'] for x in rows))
        aggregate['operator_quality_gate_pass']=aggregate['rewrite_overlap']['minimum']>=.9 and aggregate['rewrite_overlap']['p10']>=.9
        aggregates.append(aggregate)
    baseline={x['arm']:x for x in main_rows if False} # paired raw data use explicit keys below
    base_map={(x['rep'],x['trace_index']):x for x in main_rows if x['arm']=='ann50-ef128'}
    pairs=[]
    for s in configurations:
        selected=[x for x in main_rows if x['arm']==s['label'] and x['variant']>0 and not x['repeat']]
        pairs.append(dict(arm=s['label'],latency_delta_ms=stats([(x['resources']['seconds']['total']-
            base_map[(x['rep'],x['trace_index'])]['resources']['seconds']['total'])*1000 for x in selected]),
            faster_queries=sum(x['resources']['seconds']['total']<base_map[(x['rep'],x['trace_index'])]['resources']['seconds']['total'] for x in selected),
            lower_overlap_queries=sum(x['overlap']<base_map[(x['rep'],x['trace_index'])]['overlap'] for x in selected)))
    report=dict(stage='3.1',run=out.name,date='2026-10-29',protocol_sha256=sha((HERE/'protocol.json').read_bytes()),
        code_sha256={f:sha((HERE/f).read_bytes()) for f in ['candidate_engine.py','run_ablation.py','check_candidate_engine.py']},
        dataset=dict(chunks=len(snap.ids),dimension=1024,revision=1216,vector_sha256=manifest['vector_sha256'],families=16),
        request_counts=dict(measured=len(main_rows),prewarm=len(warm_rows),fill=len(fill_rows)),
        common_initialization=dict(source_load_seconds=input_seconds,import_seconds=import_seconds,
            snapshot_seconds=snap.load_seconds,snapshot_logical_bytes=snap.logical_bytes,
            id_map_note='per-engine construction included in lifecycle; mapping bytes object overhead unknown'),
        embedding=dict(model=namespace,cache_lookup_seconds=embedding_seconds,new_api_calls=0,
            network_seconds_this_replay=0,uncached_model_network_seconds=None),
        versions=dict(python=platform.python_version(),numpy=np.__version__,usearch=importlib.metadata.version('usearch'),sqlite=sqlite3.sqlite_version),
        aggregate=aggregates,paired_vs_ann50=pairs,
        limitations=['authored development replay, not unseen semantic evaluation or natural hit rate',
            'candidate match reads serialized JSON including old vectors; decoded on demand, implementation cost included',
            'known anchor future-independent prewarm is charged; production prediction not established',
            '3 temporal repetitions are not 96 independent query samples; no statistical certificate',
            'snapshot source verification does not authenticate original filesystem in real time',
            'ANN internal byte reads, physical disk/WAL amplification and Python RSS unknown',
            'one materialized snapshot and one SQLite writer; no concurrency, faults or cross-update reuse benchmark',
            'prepare includes ann_search; component times must not be summed with nested child time',
            'canonical and ANN distance counts are different operations; do not sum as equivalent cost',
            'no true warmstart, sparse activation, learned stopping, prefetch or exact certification'])
    write(out/'raw-results.json',dict(requests=main_rows,prewarm=warm_rows,fill=fill_rows,cache_write=cache_write,construct=construct))
    write(out/'summary.json',report);write(HERE/'results-summary.json',report)
    store.close()
    print(json.dumps(dict(run=out.name,requests=report['request_counts'],aggregate=[dict(arm=x['label'],
        rewrite_ms=x['rewrite_ms']['mean'],overlap=x['rewrite_overlap']['mean'],minimum=x['rewrite_overlap']['minimum'],
        lifecycle_ms=x['lifecycle_ms'],canonical=x['resources']['canonical_scores']['mean'],
        ann_distances=x['resources']['ann_distance_evaluations']['mean']) for x in aggregates]),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
