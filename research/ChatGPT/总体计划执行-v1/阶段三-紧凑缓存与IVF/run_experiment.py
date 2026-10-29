"""Finite stage3.2 replay, private inputs/output, no network client."""
from execution_engine import *
from layouts import IVF
import platform,importlib.metadata

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PRIVATE=ROOT/'.private-kb-experiments'

def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def stats(xs):
    if not xs:return None
    a=np.asarray(xs,dtype=np.float64)
    return dict(n=len(xs),mean=float(a.mean()),minimum=float(a.min()),p10=float(np.percentile(a,10)),
                p50=float(np.percentile(a,50)),p95=float(np.percentile(a,95)),maximum=float(a.max()))

def configurations(N):
    specs=[dict(label='ann50',mode='ann',layout='compact',C=0,nlist=0,budget=None),
           dict(label='full',mode='full',layout='compact',C=0,nlist=0,budget=None)]
    for layout in ('json','compact'):
        for mode in ('seed','merge'):
            for C in (10,50,200):
                specs.append(dict(label=f'{layout}-{mode}-C{C}',mode=mode,layout=layout,C=C,nlist=0,budget=None))
    for nl in (16,64):
        for budget in (128,256,512,N):
            specs.append(dict(label=f'ivf{nl}-cold-B{budget}',mode='ivf-cold',layout='compact',C=0,nlist=nl,budget=budget))
            for C in (10,50,200):
                if C<=budget:
                    specs.append(dict(label=f'ivf{nl}-warm-C{C}-B{budget}',mode='ivf-warm',layout='compact',C=C,nlist=nl,budget=budget))
    return specs

def brief(r):
    assert r.kind==ResultKind.APPROXIMATE,(r.kind,r.reason)
    return dict(ids=[x['id'] for x in r.items],resources=r.resources,cache_hit=r.cache_hit,guarantee=r.guarantee)

def load_inputs():
    t=time.perf_counter();frozen=PRIVATE/'plan-v1-stage1'
    db=sqlite3.connect((frozen/'frozen.sqlite').as_uri()+'?mode=ro',uri=True)
    rows=db.execute('SELECT d.id,d.vector,d.text,d.version,d.visible,c.path,c.start,c.end,c.start_line,c.end_line,c.file_sha '
                    'FROM docs d JOIN chunks c ON d.id=c.id ORDER BY d.id').fetchall();db.close()
    dates={r['path']:r['updated'] for r in json.loads((frozen/'source-metadata.json').read_text(encoding='utf-8'))}
    records=[dict(id=r[0],vector=np.frombuffer(r[1],dtype=np.float64),text=r[2],version=r[3],visible=r[4],
        path=r[5],updated=dates.get(r[5]),provenance=dict(start=r[6],end=r[7],start_line=r[8],end_line=r[9],
             file_sha=r[10],kind='frozen_extracted_chunk')) for r in rows]
    m=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    assert sha(np.stack([r['vector'] for r in records]).tobytes())==m['vector_sha256']
    source_seconds=time.perf_counter()-t
    namespace=json.loads((HERE.parent/'stage1_protocol.json').read_text(encoding='utf-8'))['model']
    groups=json.loads((ROOT/'ChatGPT/真实查询复用研究-v0.14/queries.json').read_text(encoding='utf-8'))
    texts=[x for g in groups for x in g];assert len(groups)==16 and len(texts)==48
    t=time.perf_counter();db=sqlite3.connect((PRIVATE/'embedding-cache.sqlite').as_uri()+'?mode=ro',uri=True)
    vectors=[]
    for text in texts:
        r=db.execute('SELECT vector FROM vectors WHERE namespace=? AND sha=?',(namespace,sha(text.encode()))).fetchone()
        if r is None:raise RuntimeError('missing cached embedding; API fallback prohibited')
        vectors.append(np.frombuffer(r[0],dtype=np.float64).copy())
    db.close()
    return records,vectors,texts,namespace,m,dict(source_seconds=source_seconds,embedding_cache_seconds=time.perf_counter()-t)

def main():
    protocol=json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    root=PRIVATE/'plan-v1-stage3-ivf';root.mkdir(exist_ok=True)
    out=next(root/f'run-{i:03d}' for i in range(1,1000) if not (root/f'run-{i:03d}').exists());out.mkdir()
    write(out/'protocol.json',protocol)
    records,vectors,texts,namespace,manifest,load=load_inputs()
    store=Store(out/'execution.sqlite',1024,namespace);load['import_seconds']=store.initialize(records,1216)
    snap=store.snapshot();load.update(snapshot_seconds=snap.load_seconds,snapshot_logical_bytes=snap.logical_bytes)
    specs=configurations(len(snap.ids));assert len(specs)==44
    # One immutable IVF layout per block count, shared by all arms and repetitions.
    ivfs={nl:IVF(snap,nl) for nl in (16,64)}
    build={str(nl):dict(seconds=v.seconds,payload_bytes=v.payload_bytes,list_sizes=v.list_sizes,
                      input_vector_bytes=snap.vectors.nbytes,scope='shared index build, reported separately from per-arm lifecycle') for nl,v in ivfs.items()}
    truth=[]
    for q in vectors:
        scores=canonical(snap.vectors,q);truth.append(snap.ids[np.lexsort((snap.ids,-scores))[:10]].tolist())
    trace=[]
    for f in range(16):
        for variant,repeated in [(0,False),(1,False),(1,True),(2,False),(2,True)]:
            trace.append(dict(family=f,query=f*3+variant,variant=variant,repeat=repeated))
    measured=[];warm=[];fills=[];writes=[];construct=[]
    for rep in range(3):
        engines={}
        for cfg in specs:
            t=time.perf_counter()
            engines[cfg['label']]=CandidateEngine(store,snap,cfg['label'],cfg['mode'],cfg['C'],
                layout=cfg['layout'],ivf=ivfs.get(cfg['nlist']),scan_budget=cfg['budget'])
            construct.append(dict(rep=rep,arm=cfg['label'],seconds=time.perf_counter()-t))
        for family in range(16):
            qi=family*3
            for cfg in specs:
                r=engines[cfg['label']].run(Request(vectors[qi],text=texts[qi]),prewarm=True)
                warm.append(dict(rep=rep,arm=cfg['label'],query=qi,**brief(r)))
        for cfg in specs:
            if cfg['C']==0:continue
            e=engines[cfg['label']];filler=Engine(store,snap,ResultCache(),candidates=cfg['C'],ef=128);filler.ann=e.ann
            for family in range(16):
                qi=family*3;r=filler.run(Request(vectors[qi],backend='ann',k=cfg['C'],use_cache=False))
                fills.append(dict(rep=rep,arm=cfg['label'],query=qi,**brief(r)))
                l=Ledger();t=time.perf_counter()
                e.seeds.put(e.bucket(Request(vectors[qi])),vectors[qi],r.items,'ann',family,l)
                l.elapsed('candidate_write',t);l.elapsed('total',t)
                writes.append(dict(rep=rep,arm=cfg['label'],query=qi,resources=l.dump()))
            filler.close()
        print(f'prewarm_fill rep={rep+1} arms=44',flush=True)
        for ti,event in enumerate(trace):
            shift=(rep+ti)%len(specs);order=specs[shift:]+specs[:shift]
            for cfg in order:
                qi=event['query'];e=engines[cfg['label']]
                cap=cfg['budget'] or (len(snap.ids) if cfg['mode']=='full' else 50+cfg['C'])
                r=e.run(Request(vectors[qi],text=texts[qi],limits={'canonical_scores':cap}))
                b=brief(r);assert len(set(b['ids']))==len(b['ids'])==10
                assert b['resources']['consumed'].get('canonical_scores',0)<=cap
                assert b['resources']['consumed']['source_reads']==10 and b['resources']['consumed']['state_commits']==1
                if cfg['mode']=='full' or cfg['budget']==len(snap.ids):assert b['ids']==truth[qi]
                measured.append(dict(rep=rep,trace_index=ti,arm=cfg['label'],**event,
                    overlap=len(set(b['ids'])&set(truth[qi]))/10,**b))
        write(out/'progress.json',dict(repetitions_completed=rep+1,measured=len(measured)))
        print(f'main_complete rep={rep+1} measured={len(measured)}',flush=True)
        for e in engines.values():e.close()
    keys=sorted({k for x in measured+warm+fills+writes for k in x['resources']['consumed']})
    aggregate=[]
    for cfg in specs:
        arm=cfg['label'];rows=[x for x in measured if x['arm']==arm]
        rw=[x for x in rows if x['variant']>0 and not x['repeat']]
        lifecycle=[x for x in measured+warm+fills+writes if x['arm']==arm]
        timing=lambda rs,k:stats([x['resources']['seconds'].get(k,0)*1000 for x in rs])
        overlap=stats([x['overlap'] for x in rw])
        aggregate.append(dict(**cfg,requests=len(rows),rewrite_ms=timing(rw,'total'),foreground_ms=timing(rows,'total'),
            rewrite_overlap=overlap,quality_gate=overlap['minimum']>=.9 and overlap['p10']>=.9,
            unique_rewrites_below90=sum(x['overlap']<.9 for x in rw if x['rep']==0),
            components_ms={k:timing(rw,k) for k in ['prepare','candidate_match','seed_validation','coarse','ivf_frontier','ann_search','seed_score','canonical_score','source_fetch','state_commit']},
            counters={k:stats([x['resources']['consumed'].get(k,0) for x in rw]) for k in keys},
            cache_hits=sum(x['cache_hit'] for x in rows),
            peak_candidate_payload=max(x['guarantee']['candidate_cache_payload_bytes'] for x in rows),
            lifecycle_excluding_shared_ivf_ms=sum(x['resources']['seconds']['total']*1000 for x in lifecycle)+sum(x['seconds']*1000 for x in construct if x['arm']==arm),
            initialization=dict(prewarm_ms=sum(x['resources']['seconds']['total']*1000 for x in warm if x['arm']==arm),
                candidate_fill_ms=sum(x['resources']['seconds']['total']*1000 for x in fills if x['arm']==arm),
                candidate_write_ms=sum(x['resources']['seconds']['total']*1000 for x in writes if x['arm']==arm)),
            per_rep=[dict(rep=i,rewrite_mean_ms=float(np.mean([x['resources']['seconds']['total']*1000 for x in rw if x['rep']==i])),
                overlap_mean=float(np.mean([x['overlap'] for x in rw if x['rep']==i]))) for i in range(3)]))
    controls=[]
    for mode in ('seed','merge'):
        for C in (10,50,200):
            a={ (x['rep'],x['query']):x['ids'] for x in fills if x['arm']==f'json-{mode}-C{C}'}
            b={ (x['rep'],x['query']):x['ids'] for x in fills if x['arm']==f'compact-{mode}-C{C}'}
            ra={(x['rep'],x['trace_index']):x['ids'] for x in measured if x['arm']==f'json-{mode}-C{C}'}
            rb={(x['rep'],x['trace_index']):x['ids'] for x in measured if x['arm']==f'compact-{mode}-C{C}'}
            controls.append(dict(mode=mode,C=C,identical_filled_seed_sets=a==b,
                                 identical_replay_results=ra==rb))
    report=dict(stage='3.2',run=out.name,date='2026-10-29',protocol_sha256=sha((HERE/'protocol.json').read_bytes()),
        code_sha256={f:sha((HERE/f).read_bytes()) for f in ['execution_engine.py','layouts.py','checks.py','run_experiment.py']},
        request_counts=dict(measured=len(measured),prewarm=len(warm),fill=len(fills)),
        dataset=dict(chunks=len(snap.ids),dimension=1024,revision=1216,families=16,vector_sha256=manifest['vector_sha256']),
        embedding=dict(model=namespace,new_api_calls=0,uncached_network_seconds=None),common_initialization=load,ivf_build=build,
        versions=dict(python=platform.python_version(),numpy=np.__version__,sklearn=importlib.metadata.version('scikit-learn'),usearch=importlib.metadata.version('usearch')),
        aggregate=aggregate,layout_controls=controls,
        limitations=['same 16 old authored development families, unreviewed semantic labels; no iid confidence claim',
            'same fixed vector budget includes seed scoring, coarse work counted separately; no geometric bound early stop',
            'posting-list Python loop and SQLite FULL commit are reference implementation costs, not algorithm lower bounds',
            'compact bank retains full-bank read/copy policy; no free selected-payload lookup',
            'common IVF build physically shared and separately reported; per-arm lifecycle excludes this common build',
            'ordinary warmup uses mature ANN for all nonfull arms; ANN indexes retained during replay and their setup is charged',
            'snapshot/source verification does not check original filesystem; physical IO/RSS and OS amplification unknown',
            'no model training, prefetch, strict certification, cold disk/concurrency/fault or cross-update reuse experiments'])
    write(out/'raw-results.json',dict(requests=measured,prewarm=warm,fill=fills,writes=writes,construct=construct))
    write(out/'summary.json',report);write(HERE/'results-summary.json',report);store.close()
    print(json.dumps(dict(run=out.name,counts=report['request_counts'],layout_controls=controls,
        rows=[dict(label=x['label'],ms=x['rewrite_ms']['mean'],overlap=x['rewrite_overlap']['mean'],minimum=x['rewrite_overlap']['minimum'],
            canonical=x['counters']['canonical_scores']['mean'],quality_gate=x['quality_gate']) for x in aggregate]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
