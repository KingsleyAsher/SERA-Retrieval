"""Stage3.2 executor, derived from frozen stage3.1; old sources remain unchanged."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'阶段二'))
from framework import *
from layouts import CandidateBank


class CandidateCache:
    def __init__(self, capacity=16, max_bytes=4*1024*1024):
        self.capacity, self.max_bytes = capacity, max_bytes
        self.data = OrderedDict()
        self.bytes = 0

    def put(self, bucket, q, items, origin, sequence, ledger):
        entry = dict(bucket=bucket, q=q.tolist(), query_sha=sha(q.tobytes()),
                     seeds=[[int(x['id']),int(x['version'])] for x in items],
                     origin=origin, sequence=sequence)
        key = sha(packed([bucket,entry['query_sha'],sequence]).encode())
        payload = packed(entry)
        size = len(key.encode())+len(payload.encode())
        ledger.charge(candidate_writes=1,candidate_bytes_written=size)
        if size>self.max_bytes:
            raise ValueError('candidate exceeds fixed cache capacity')
        old = self.data.pop(key,None)
        if old is not None: self.bytes -= len(key.encode())+len(old.encode())
        self.data[key]=payload; self.bytes+=size
        while len(self.data)>self.capacity or self.bytes>self.max_bytes:
            k,v=self.data.popitem(last=False); self.bytes-=len(k.encode())+len(v.encode())
        return key


class CandidateEngine(Engine):
    def __init__(self, store, snapshot, label, mode='ann', C=0, candidates=50, ef=128, layout='compact', ivf=None, scan_budget=None):
        super().__init__(store,snapshot,ResultCache(),candidates,ef)
        self.label,self.mode,self.C=label,mode,C
        self.seeds=CandidateBank(layout)
        self.ivf,self.scan_budget=ivf,scan_budget
        if ivf is not None and ivf.snapshot!=snapshot.identity:raise ValueError('foreign IVF snapshot')
        self.id_positions={int(i):p for p,i in enumerate(snapshot.ids)}
        self.position_map_seconds=0.0  # caller records construction wall time

    def bucket(self, req):
        return sha(packed([self.snap.identity,self.snap.model,SCORE,asdict(req.scope),req.k]).encode())

    def search(self, q, allowed, ledger):
        if not allowed: return []
        a=np.asarray(allowed,dtype=np.int64)
        admission=dict(ann_calls=1)
        if sha(a.tobytes()) not in self.ann:
            admission.update(index_builds=1,index_input_vector_bytes=len(a)*self.store.dim*4)
        ledger.charge(**admission)
        index=self.ensure_ann(a,ledger,prepaid=True)
        t=time.perf_counter()
        found=index.search(q.astype(np.float32),count=min(self.candidates,len(a)),threads=1)
        ledger.elapsed('ann_search',t)
        ledger.charge(ann_distance_evaluations=int(found.computed_distances),
                      ann_visited_members=int(found.visited_members))
        return [int(x) for x in found.keys]

    def score_batch(self,state,q,batch,ledger,seed=False):
        admission=dict(canonical_scores=len(batch),vector_logical_bytes=len(batch)*self.store.dim*8)
        new_lists=[]
        if state.backend.startswith('ivf-'):
            old=set(state.request_data['reuse'].get('scored_lists',[]))
            new_lists=sorted(set(int(self.ivf.assignment[p]) for p in batch)-old)
            admission['ivf_lists_scored']=len(new_lists)
        ledger.charge(**admission)
        ts=time.perf_counter();values=canonical(self.snap.vectors[batch],q)
        state.scored.extend([[int(p),float(v)] for p,v in zip(batch,values)])
        state.cursor+=len(batch)
        reuse=state.request_data['reuse']
        if state.backend.startswith('ivf-'):
            reuse.setdefault('scored_lists',[]).extend(new_lists)
            ledger.charge(**({'seed_scores':len(batch)} if seed else {'ivf_scanned_scores':len(batch)}))
        ledger.elapsed('seed_score' if seed else 'canonical_score',ts)

    def run(self, req, state=None, prewarm=False):
        start=time.perf_counter()
        ledger=Ledger(req.limits,state.consumed if state else None)
        mode=('full' if self.mode=='full' else 'ann') if prewarm else self.mode
        try:
            q=valid_vector(req.vector,self.store.dim)
            if req.score_contract!=SCORE or req.quality!='empirical' or req.k<1:
                raise ValueError('unsupported score/quality/K')
            if mode.startswith('ivf-') and (self.ivf is None or not isinstance(self.scan_budget,int) or self.scan_budget<1):
                raise ValueError('IVF and positive vector scan budget required')
            if req.snapshot is not None and req.snapshot!=self.snap.identity:
                raise ValueError('snapshot mismatch')
            if req.snapshot is None and state is None and self.store.latest()!=self.snap.revision:
                raise ValueError('stale executor')
            supported={'canonical_scores','vector_logical_bytes','metadata_checks','source_reads',
                'source_logical_bytes','materialized_text_checks','cache_lookups','result_cache_hits',
                'index_builds','index_input_vector_bytes','ann_calls','state_commits',
                'candidate_cache_lookups','candidate_bytes_read','seed_verifications',
                'seed_payload_reads','candidate_entries_checked','coarse_scores','coarse_vector_bytes',
                'ivf_posting_checks','ivf_posting_bytes','ivf_lists_opened','ivf_lists_scored'}
            if any(k not in supported or not isinstance(v,int) or v<0 for k,v in req.limits.items()):
                raise ValueError('unsupported hard budget; native ANN work is observed only')
            if req.scope.updated_on_or_before is not None:
                datetime.date.fromisoformat(req.scope.updated_on_or_before)
            cachekey=sha(packed([self.snap.identity,self.label,self.snap.model,SCORE,
                asdict(req.scope),req.k,sha(q.tobytes())]).encode())
            signature=sha(packed([cachekey,mode,self.scan_budget,self.ivf.nlist if self.ivf else None]).encode())
            if state is not None:
                self.store.validate_state_owner(state)
                if state.signature!=signature or state.snapshot!=self.snap.identity:
                    raise ValueError('checkpoint request mismatch')
                if any(state.consumed.get(k,0)>v for k,v in req.limits.items()):
                    raise ValueError('resume below already consumed resources')
            else:
                state=Execution(signature,self.snap.identity,mode,
                    request_data=dict(reuse={},mode=mode,cachekey=cachekey))
        except (ValueError,TypeError) as exc:
            return Result(ResultKind.REJECTED,self.snap.identity,SCORE,[],{},ledger.dump(),reason=str(exc))
        reuse=state.request_data['reuse']
        try:
            if state.phase=='prepare':
                t=time.perf_counter()
                try:
                    while state.phase=='prepare':
                        step=state.prepare_step
                        if step=='lookup':
                            ledger.charge(cache_lookups=int(req.use_cache))
                            cached=self.cache.get(cachekey) if req.use_cache else None
                            if cached is not None:
                                state.selected=cached;state.cache_hit=True;state.prepare_step='cache_return'
                            else: state.prepare_step='scope'
                        elif step=='cache_return':
                            ledger.charge(result_cache_hits=1);state.phase='sources'
                        elif step=='scope':
                            ledger.charge(metadata_checks=len(self.snap.rows))
                            state.allowed=self.snap.allowed(req.scope).tolist()
                            if mode=='full':
                                state.positions=state.allowed.copy();state.phase='score'
                            else: state.prepare_step='match' if mode in ('seed','merge','ivf-warm') else 'ann'
                        elif step=='match':
                            reuse.update(self.seeds.match(self.bucket(req),q,ledger))
                            state.prepare_step='validate'
                        elif step=='validate':
                            allowed=set(state.allowed);seen=set(state.positions)
                            while reuse['cursor']<len(reuse['seeds']):
                                ledger.charge(seed_verifications=1)
                                ts=time.perf_counter()
                                ident,version=reuse['seeds'][reuse['cursor']]
                                p=self.id_positions.get(ident)
                                if p is not None and p in allowed and self.snap.rows[p]['version']==version:
                                    if p not in seen:state.positions.append(p);seen.add(p)
                                    reuse['verified']+=1
                                else: reuse['stale']+=1
                                reuse['cursor']+=1
                                ledger.elapsed('seed_validation',ts)
                            # A short seed pool has an executable fallback in this same parent budget.
                            state.prepare_step='seed_score' if mode=='ivf-warm' else ('ann' if mode=='merge' or len(state.positions)<min(req.k,len(state.allowed)) else 'ready')
                        elif step=='seed_score':
                            if len(state.positions)>self.scan_budget:
                                raise ValueError('seed pool exceeds admitted scan budget')
                            if state.cursor<len(state.positions):
                                if req.deadline_ms is not None and (time.perf_counter()-start)*1000>=req.deadline_ms:
                                    raise Exhausted('soft deadline')
                                available=ledger.limits.get('canonical_scores',float('inf'))-ledger.consumed.get('canonical_scores',0)
                                n=int(min(64,len(state.positions)-state.cursor,available))
                                if n<=0:raise Exhausted('canonical_scores')
                                self.score_batch(state,q,state.positions[state.cursor:state.cursor+n],ledger,seed=True)
                            else:state.prepare_step='coarse'
                        elif step=='coarse':
                            target=min(self.scan_budget,len(state.allowed))
                            if target<min(req.k,len(state.allowed)):
                                raise ValueError('scan budget cannot produce requested eligible K')
                            ledger.charge(coarse_scores=self.ivf.nlist,
                                coarse_vector_bytes=self.ivf.centers.nbytes)
                            ts=time.perf_counter();priorities=canonical(self.ivf.centers,q)
                            if mode=='ivf-warm':
                                for p,value in state.scored:
                                    j=int(self.ivf.assignment[p]);priorities[j]=max(priorities[j],value)
                            reuse.update(order=sorted(range(self.ivf.nlist),key=lambda j:(-float(priorities[j]),j)),
                                         list_cursor=0,member_cursor=0,opened=[],target=target)
                            ledger.elapsed('coarse',ts);state.prepare_step='frontier'
                        elif step=='frontier':
                            seen=set(state.positions);allowed=set(state.allowed)
                            ts=time.perf_counter()
                            try:
                                while len(state.positions)<reuse['target'] and reuse['list_cursor']<len(reuse['order']):
                                    j=reuse['order'][reuse['list_cursor']];members=self.ivf.lists[j]
                                    if j not in reuse['opened']:
                                        ledger.charge(ivf_lists_opened=1);reuse['opened'].append(j)
                                    if reuse['member_cursor']>=len(members):
                                        reuse['list_cursor']+=1;reuse['member_cursor']=0;continue
                                    ledger.charge(ivf_posting_checks=1,ivf_posting_bytes=8)
                                    p=int(members[reuse['member_cursor']]);reuse['member_cursor']+=1
                                    if p in allowed and p not in seen:state.positions.append(p);seen.add(p)
                            finally:ledger.elapsed('ivf_frontier',ts)
                            state.prepare_step='ready'
                        elif step=='ann':
                            if mode.startswith('ivf-'):
                                state.prepare_step='coarse';continue
                            found=self.search(q,state.allowed,ledger)
                            seen=set(state.positions)
                            state.positions.extend(p for p in found if p not in seen)
                            state.actions.append(Action.SEARCH_EXPAND.value)
                            state.prepare_step='ready'
                        elif step=='ready':
                            if len(state.positions)!=len(set(state.positions)):
                                raise ValueError('duplicate scoring positions')
                            reuse['candidate_count']=len(state.positions)
                            state.phase='score'
                        else: raise ValueError('invalid prepare step')
                finally:ledger.elapsed('prepare',t)
            while state.phase=='score' and state.cursor<len(state.positions):
                if req.deadline_ms is not None and (time.perf_counter()-start)*1000>=req.deadline_ms:
                    raise Exhausted('soft deadline')
                remaining=ledger.limits.get('canonical_scores',float('inf'))-ledger.consumed.get('canonical_scores',0)
                n=int(min(64,len(state.positions)-state.cursor,remaining))
                if n<=0:raise Exhausted('canonical_scores')
                batch=state.positions[state.cursor:state.cursor+n]
                self.score_batch(state,q,batch,ledger)
            if state.phase=='score':
                ts=time.perf_counter()
                ranked=sorted(state.scored,key=lambda x:(-x[1],int(self.snap.ids[x[0]])))
                state.selected=ranked[:req.k];state.phase='sources'
                state.actions.append(Action.CANDIDATE_RESCORE.value if mode=='seed' else Action.EXACT_RERANK.value)
                ledger.elapsed('rank',ts)
            while state.phase=='sources' and len(state.sources)<len(state.selected):
                p,score=state.selected[len(state.sources)];row=self.snap.rows[p]
                ledger.charge(source_reads=1,source_logical_bytes=len(row['text'].encode()),materialized_text_checks=1)
                ts=time.perf_counter()
                if not row['visible'] or sha(row['text'].encode())!=row['content_sha']:
                    raise ValueError('invalid source in pinned snapshot')
                state.sources.append(dict(id=int(self.snap.ids[p]),version=row['version'],score=score,
                    path=row['path'],content_sha=row['content_sha'],provenance=row['provenance'],text=row['text'],
                    source_verification=dict(snapshot_content=True,original_file=False)))
                ledger.elapsed('source_fetch',ts)
            if state.phase=='sources':state.phase='commit'
            if state.phase=='commit':
                # Compact, common completion record; seed payload no longer needed after completion.
                reuse.pop('seeds',None)
                state.positions=[];state.scored=[]
                self.store.save(state,ledger);state.phase='done'
            if req.use_cache:self.cache.put(cachekey,state.selected)
            ledger.elapsed('total',start)
            return Result(ResultKind.APPROXIMATE,self.snap.identity,SCORE,state.sources,
                dict(scope='exhaustive_under_canonical_f64' if mode=='full' else 'empirical_approximate',
                    strict_certificate=False,semantic_quality='unreviewed',reuse=dict(reuse),
                    candidate_cache_payload_bytes=self.seeds.bytes,result_cache_payload_bytes=self.cache.bytes,
                    ivf_payload_bytes=self.ivf.payload_bytes if self.ivf else 0,
                    index_resident_bytes=sum(int(x.memory_usage) for x in self.ann.values()),
                    ann_internal_read_bytes=None),ledger.dump(),cache_hit=state.cache_hit)
        except Exhausted as exc:
            state.consumed=ledger.consumed.copy();ledger.elapsed('total',start)
            return Result(ResultKind.PENDING,self.snap.identity,SCORE,[],dict(strict_certificate=False),
                          ledger.dump(),state,str(exc))
        except ValueError as exc:
            ledger.elapsed('total',start)
            return Result(ResultKind.REJECTED,self.snap.identity,SCORE,[],{},ledger.dump(),reason=str(exc))
