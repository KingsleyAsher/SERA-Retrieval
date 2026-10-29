"""Reproducible stage-two engineering benchmark; private inputs/outputs stay private."""
from framework import *
import platform, importlib.metadata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIVATE = ROOT/'.private-kb-experiments'
FROZEN = PRIVATE/'plan-v1-stage1'
P = json.loads((HERE/'stage2_protocol.json').read_text(encoding='utf-8'))

def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def summary(values):
    return dict(n=len(values), mean=float(np.mean(values)), p50=float(np.percentile(values,50)),
                p95=float(np.percentile(values,95)), minimum=float(min(values)), maximum=float(max(values)))

def main():
    runroot = PRIVATE/'plan-v1-stage2'
    runroot.mkdir(exist_ok=True)
    run_id = next(f'run-{i:03d}' for i in range(1,1000) if not (runroot/f'run-{i:03d}').exists())
    out = runroot/run_id; out.mkdir()
    write(out/'protocol.json', P)
    t = time.perf_counter()
    db = sqlite3.connect((FROZEN/'frozen.sqlite').as_uri()+'?mode=ro', uri=True)
    rows = db.execute('SELECT d.id,d.vector,d.text,d.version,d.visible,c.path,c.start,c.end,c.start_line,c.end_line,c.file_sha '
        'FROM docs d JOIN chunks c ON d.id=c.id ORDER BY d.id').fetchall()
    db.close()
    source_load_seconds = time.perf_counter()-t
    dates = {r['path']:r['updated'] for r in json.loads((FROZEN/'source-metadata.json').read_text(encoding='utf-8'))}
    records = [dict(id=r[0], vector=np.frombuffer(r[1], dtype=np.float64), text=r[2], version=r[3], visible=r[4],
        path=r[5], updated=dates.get(r[5]), provenance=dict(start=r[6],end=r[7],start_line=r[8],end_line=r[9],file_sha=r[10],
        kind='frozen_extracted_chunk')) for r in rows]
    manifest = json.loads((FROZEN/'manifest.json').read_text(encoding='utf-8'))
    assert sha(np.stack([r['vector'] for r in records]).tobytes()) == manifest['vector_sha256']
    namespace = json.loads((HERE.parent/'stage1_protocol.json').read_text(encoding='utf-8'))['model']
    # No credential or network client needed: existing vectors only, cache misses fail.
    groups = json.loads((ROOT/'ChatGPT/真实查询复用研究-v0.14/queries.json').read_text(encoding='utf-8'))
    texts = [text for group in groups for text in group]
    embedding_db = sqlite3.connect((PRIVATE/'embedding-cache.sqlite').as_uri()+'?mode=ro', uri=True)
    query_vectors=[]
    t=time.perf_counter()
    for text in texts:
        row = embedding_db.execute('SELECT vector FROM vectors WHERE namespace=? AND sha=?',
                                   (namespace, sha(text.encode()))).fetchone()
        if row is None:
            raise RuntimeError('existing embedding missing; no automatic API fallback')
        query_vectors.append(np.frombuffer(row[0],dtype=np.float64).copy())
    embedding_lookup_seconds=time.perf_counter()-t
    embedding_db.close()
    assert len(query_vectors)==48
    store = Store(out/'execution.sqlite',1024,namespace)
    import_seconds = store.initialize(records,1216)
    snap = store.snapshot()
    cache = ResultCache(P['cache_capacity_entries'])
    engines={b:Engine(store,snap,cache,candidates=P['candidates'],ef=P['hnsw']['expansion_search']) for b in ('full','ann','hybrid')}
    truth=[]
    for q in query_vectors:
        values=canonical(snap.vectors,q)
        truth.append(snap.ids[np.lexsort((snap.ids,-values))[:10]].tolist())
    raw=[]
    for rep in range(P['repetitions']):
        for qi,(text,q) in enumerate(zip(texts,query_vectors)):
            backend_order=list(engines)
            shift=(rep+qi)%3
            backend_order=backend_order[shift:]+backend_order[:shift]
            for backend in backend_order:
                req=Request(q,backend=backend,text=text,use_cache=False,
                            score_contract=HYBRID_SCORE if backend=='hybrid' else SCORE)
                result=engines[backend].run(req)
                assert result.kind==ResultKind.APPROXIMATE
                ids=[item['id'] for item in result.items]
                if backend=='full':
                    assert ids==truth[qi]
                assert len(set(ids))==len(ids)==10
                raw.append(dict(rep=rep,query=qi,backend=backend,ids=ids,
                    overlap=len(set(ids)&set(truth[qi]))/10,resources=result.resources,
                    guarantee=result.guarantee))
    print('main_requests_complete',len(raw),flush=True)

    # Common exact-result cache, charged source reads and same commit path.
    cache_rows=[]
    for backend,engine in engines.items():
        for i in range(4):
            req=Request(query_vectors[i],backend=backend,text=texts[i],
                        score_contract=HYBRID_SCORE if backend=='hybrid' else SCORE)
            first=engine.run(req); second=engine.run(req)
            assert second.cache_hit and [r['id'] for r in first.items]==[r['id'] for r in second.items]
            cache_rows.append(dict(backend=backend,query=i,miss=first.resources,hit=second.resources))

    # Engineering filter checks on existing metadata, not semantic label tests.
    prefixes=list(dict.fromkeys(r['path'].replace('\\','/').split('/')[0]+'/' for r in snap.rows))[:2]
    scopes=[Scope(p) for p in prefixes]+[Scope('', '2026-10-28'),Scope('no-such-source/')]
    filters=[]
    for si,scope in enumerate(scopes):
        permitted=set(snap.allowed(scope).tolist())
        for backend,engine in engines.items():
            result=engine.run(Request(query_vectors[0],backend=backend,text=texts[0],scope=scope,
                score_contract=HYBRID_SCORE if backend=='hybrid' else SCORE,use_cache=False))
            assert result.kind==ResultKind.APPROXIMATE
            assert all(int(np.searchsorted(snap.ids,r['id'])) in permitted for r in result.items)
            filters.append(dict(scope_number=si,backend=backend,eligible=len(permitted),returned=len(result.items),resources=result.resources))

    # Measure materialization separately with all backends allowed the same resident layout.
    reload_times=[]
    for _ in range(5):
        fresh=store.snapshot(); reload_times.append(fresh.load_seconds)
        assert fresh.identity==snap.identity

    # Controlled updates: existing BGE vectors reused, synthetic text only. This
    # verifies update mechanics, not semantic correctness of edited embeddings.
    a,b,c=map(int,snap.ids[:3]); added=int(snap.ids.max())+1
    ops=[dict(op='delete',id=a),
         dict(op='put',id=b,vector=query_vectors[1],text='【虚构夹具】修改传播验证',path='__fixture__/modified.md',
              provenance=dict(kind='virtual_update_fixture')),
         dict(op='put',id=c,vector=query_vectors[0],text='【虚构夹具】不可见项',path='__fixture__/hidden.md',visible=False,
              provenance=dict(kind='virtual_update_fixture')),
         dict(op='put',id=added,vector=query_vectors[0],text='【虚构夹具】新增传播验证',path='__fixture__/append.md',
              provenance=dict(kind='virtual_update_fixture'))]
    rev,update_cost=store.mutate('stage2-controlled-update',ops)
    new=store.snapshot()
    updates=[]
    for backend in engines:
        e=Engine(store,new,cache,candidates=50,ef=128)
        for qi in (0,1):
            result=e.run(Request(query_vectors[qi],backend=backend,text=texts[qi],use_cache=True,
                score_contract=HYBRID_SCORE if backend=='hybrid' else SCORE))
            assert not result.cache_hit
            ids=[r['id'] for r in result.items]
            assert a not in ids and c not in ids
            if qi==0 and backend!='hybrid':
                assert added in ids
            if qi==1 and backend!='hybrid':
                assert any(r['id']==b and r['text']=='【虚构夹具】修改传播验证' for r in result.items)
            updates.append(dict(backend=backend,query=qi,resources=result.resources))
        e.close()
    assert snap.identity!=new.identity and a in snap.ids and a not in new.ids
    assert snap.rows[1]['text']!=new.rows[int(np.searchsorted(new.ids,b))]['text']

    agg=[]
    for backend in engines:
        subset=[r for r in raw if r['backend']==backend]
        warm=[r for r in subset if not r['resources']['consumed'].get('index_builds') and not r['resources']['consumed'].get('lexical_builds')]
        def timing(rows,key):
            return summary([r['resources']['seconds'].get(key,0)*1000 for r in rows])
        resources={key:summary([r['resources']['consumed'].get(key,0) for r in subset]) for key in
            ['canonical_scores','vector_logical_bytes','source_logical_bytes','state_payload_bytes','ann_distance_evaluations','ann_visited_members']}
        agg.append(dict(backend=backend,score_contract=HYBRID_SCORE if backend=='hybrid' else SCORE,
            requests=len(subset),all_total_ms=timing(subset,'total'),warm_total_ms=timing(warm,'total'),
            component_ms={k:timing(warm,k) for k in ['prepare','canonical_score','rank','source_fetch','state_commit']},
            exact_vector_overlap=summary([r['overlap'] for r in subset]),resources=resources,
            strict_certificates=0,semantic_quality=None))
    cache_summary=[]
    for backend in engines:
        selected=[r for r in cache_rows if r['backend']==backend]
        cache_summary.append(dict(backend=backend,requests=len(selected),
            miss_ms=summary([r['miss']['seconds']['total']*1000 for r in selected]),
            hit_ms=summary([r['hit']['seconds']['total']*1000 for r in selected]),
            hit_canonical_scores=sum(r['hit']['consumed'].get('canonical_scores',0) for r in selected),
            source_reads_on_hits=sum(r['hit']['consumed'].get('source_reads',0) for r in selected)))
    result=dict(stage=2,run=run_id,run_date='2026-10-29',
        code_sha256={name:sha((HERE/name).read_bytes()) for name in ['framework.py','run_stage2.py']},
        protocol_sha256=sha((HERE/'stage2_protocol.json').read_bytes()),
        dataset=dict(chunks=len(snap.ids),dimension=1024,revision=snap.revision,vector_sha256=manifest['vector_sha256']),
        initialization=dict(source_sqlite_materialize_seconds=source_load_seconds,isolated_import_commit_seconds=import_seconds,
            snapshot_materialize_seconds=snap.load_seconds,snapshot_logical_bytes=snap.logical_bytes,
            snapshot_materialize_repeat_ms=summary([v*1000 for v in reload_times]),
            backends={b:e.initialization for b,e in engines.items()}),
        embedding=dict(model=namespace,cache_inputs=len(texts),cache_lookup_seconds=embedding_lookup_seconds,
                       new_api_calls=0,network_seconds=0),
        aggregate=agg,cache=cache_summary,filter_checks=len(filters),controlled_update_requests=len(updates),
        update=dict(revision=rev,commit=update_cost,new_snapshot_load_seconds=new.load_seconds,
                    internal_ANN_maintenance='new snapshot index rebuilt on first use; cost charged',
                    vectors='existing BGE-M3 query vectors reused for fictitious mechanics fixtures, no semantic evaluation'),
        versions=dict(python=platform.python_version(),numpy=np.__version__,usearch=importlib.metadata.version('usearch'),sqlite=sqlite3.sqlite_version),
        limitations=['authored old diagnostic queries, no natural trace or reviewed semantic gold',
            'warm local CPU and SQLite FULL commits, no cold disk or concurrency benchmark',
            'RRF hybrid is a different scoring contract; vector overlap is not semantic quality',
            'ANN distance/visited counts exposed; internal byte reads and lexical internal postings work unknown',
            'logical byte counts omit Python object allocator overhead and physical OS/WAL amplification',
            'all backends share resident layout and ordinary result LRU; gains are engineering, not architecture novelty',
            'stage-three mechanisms and stage-four certification not enabled; no formal quality uplift',
            'no process fault injection or power-loss validation'])
    write(out/'raw-results.json',dict(requests=raw,cache=cache_rows,filters=filters,updates=updates))
    write(out/'summary.json',result)
    write(HERE/'results-summary.json',result)
    for e in engines.values(): e.close()
    store.close()
    print(json.dumps(dict(run=run_id,requests=len(raw),new_api_calls=0,
        aggregate=[dict(backend=r['backend'],warm_mean_ms=r['warm_total_ms']['mean'],
            warm_p95_ms=r['warm_total_ms']['p95'],vector_overlap=r['exact_vector_overlap']['mean'])
            for r in agg]),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
