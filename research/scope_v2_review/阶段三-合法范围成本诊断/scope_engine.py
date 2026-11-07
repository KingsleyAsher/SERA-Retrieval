"""Single-directory execution diagnostic; common timing, sources and compact commits."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'阶段二'))
from framework import *
from contextlib import contextmanager


def directory_prefix(value):
    value=value.replace('\\','/')
    if not value or not value.endswith('/') or any(x in ('.','..') for x in value.split('/')):
        raise ValueError('explicit canonical trailing-separator directory required')
    return value


class DirectoryIndex:
    def __init__(self,snap,max_bytes=1048576):
        ts=time.perf_counter();self.snapshot=snap.identity;groups={};path_bytes=0
        for p,row in enumerate(snap.rows):
            path=row['path'].replace('\\','/');path_bytes+=len(path.encode())
            if not row['visible']:continue
            for i,ch in enumerate(path):
                if ch=='/':groups.setdefault(path[:i+1],[]).append(p)
        self.data={key:np.array(value,dtype=np.int64) for key,value in groups.items()}
        self.payload_bytes=sum(len(k.encode())+v.nbytes for k,v in self.data.items())
        if self.payload_bytes>max_bytes:raise ValueError('directory payload exceeds frozen cap')
        for v in self.data.values():v.flags.writeable=False
        self.build_seconds=time.perf_counter()-ts
        self.build_counts=dict(metadata_rows=len(snap.rows),path_bytes=path_bytes,
                               directory_entries=len(self.data),posting_entries=sum(len(v) for v in self.data.values()))

    def resolve(self,prefix,ledger):
        value=self.data.get(prefix)
        count=len(value) if value is not None else 0
        ledger.charge(scope_index_lookups=1,scope_key_bytes=len(prefix.encode()),scope_posting_bytes=count*8)
        return value.copy().tolist() if value is not None else []


class Clock:
    def __init__(self):self.phases={}
    @contextmanager
    def measure(self,name):
        t=time.perf_counter()
        try:yield
        finally:self.phases[name]=self.phases.get(name,0)+time.perf_counter()-t
    def resources(self,ledger,start):
        total=time.perf_counter()-start
        other=total-sum(self.phases.values())
        if other<0:raise RuntimeError('exclusive timing segments overlap')
        r=ledger.dump();r['nested_internal_seconds']=r.pop('seconds')
        r['seconds']=dict(self.phases,other=other,total=total)
        return r


class ScopeEngine(Engine):
    def __init__(self,store,snap,label,backend,index,geometry=None,target=512,candidates=50,ef=128,row_scan=False):
        super().__init__(store,snap,ResultCache(),candidates,ef)
        if backend not in ('full','ivf','ann') or index.snapshot!=snap.identity:
            raise ValueError('backend/directory index mismatch')
        if backend=='ivf' and (geometry is None or geometry.snapshot!=snap.identity):
            raise ValueError('IVF snapshot mismatch')
        self.label,self.backend,self.directory,self.geometry,self.target,self.row_scan=label,backend,index,geometry,target,row_scan
        self.geometry_hash=(sha(geometry.centers.tobytes()+geometry.assignment.tobytes()+
            b''.join(m.tobytes() for m in geometry.lists)) if geometry is not None else None)

    def checkpoint(self,state):
        if state.snapshot!=self.snap.identity or state.request_data.get('executor')!='scope-v1':
            raise ValueError('checkpoint scope contract mismatch')
        return self.store.save(state,Ledger(state.request_data['limits'],state.consumed))

    def run(self,req,state=None,*,budget_change_reason=None):
        start=time.perf_counter();clock=Clock();ledger=Ledger(req.limits,state.consumed if state else None)
        try:
            with clock.measure('validate'):
                q=valid_vector(req.vector,self.store.dim)
                if (req.k<1 or req.score_contract!=SCORE or req.quality!='empirical' or req.use_cache
                        or req.scope.updated_on_or_before is not None):
                    raise ValueError('unsupported K/score/quality/cache/date configuration')
                prefix=directory_prefix(req.scope.source_prefix)
                if req.snapshot is not None and req.snapshot!=self.snap.identity:raise ValueError('snapshot mismatch')
                if state is None and req.snapshot is None and self.store.latest()!=self.snap.revision:raise ValueError('stale snapshot')
                supported={'canonical_scores','vector_logical_bytes','source_reads','source_logical_bytes',
                    'materialized_text_checks','state_commits','ann_calls','index_builds','index_input_vector_bytes',
                    'metadata_checks','scope_index_lookups','scope_key_bytes','scope_posting_bytes',
                    'coarse_scores','coarse_vector_bytes','ivf_posting_checks','ivf_posting_bytes','ivf_lists_opened'}
                if any(k not in supported or type(v) is not int or v<0 for k,v in req.limits.items()):
                    raise ValueError('unsupported hard cap; native ANN distance count is observed only')
                signature=sha(packed(['scope-v1',self.snap.identity,self.label,self.backend,prefix,req.k,SCORE,
                    sha(q.tobytes()),self.target,self.candidates,self.ef,self.geometry_hash]).encode())
                if state is None:
                    state=Execution(signature,self.snap.identity,self.backend,prepare_step='scope',
                        request_data=dict(executor='scope-v1',scope_known=False,limits=req.limits.copy(),budget_changes=[]))
                else:
                    self.store.validate_state_owner(state)
                    if state.signature!=signature:raise ValueError('query/scope/backend checkpoint mismatch')
                    if any(state.consumed.get(k,0)>v for k,v in req.limits.items()):raise ValueError('budget below consumed')
                    prior=state.request_data['limits']
                    relax=[k for k,v in prior.items() if req.limits.get(k,float('inf'))>v]
                    if relax and (not isinstance(budget_change_reason,str) or not budget_change_reason.strip()):
                        raise ValueError('explicit caller budget addition required')
                    if prior!=req.limits:
                        state.request_data['budget_changes'].append(dict(prior=prior.copy(),new=req.limits.copy(),reason=budget_change_reason))
                    state.request_data['limits']=req.limits.copy()
            f=state.request_data
            while state.phase=='prepare':
                if req.deadline_ms is not None and (time.perf_counter()-start)*1000>=req.deadline_ms:raise Exhausted('soft deadline')
                step=state.prepare_step
                if step=='scope':
                    with clock.measure('scope_resolve'):
                        if self.row_scan:
                            ledger.charge(metadata_checks=len(self.snap.rows))
                            state.allowed=self.snap.allowed(Scope(prefix)).tolist()
                        else:state.allowed=self.directory.resolve(prefix,ledger)
                        f.update(scope_known=True,eligible=len(state.allowed))
                        if self.backend=='full':state.positions=state.allowed.copy();state.phase='score'
                        else:state.prepare_step='coarse' if self.backend=='ivf' else 'ann'
                elif step=='coarse':
                    with clock.measure('coarse'):
                        target=min(self.target,len(state.allowed))
                        if target<min(req.k,len(state.allowed)):raise ValueError('fixed target cannot produce legal K')
                        ledger.charge(coarse_scores=self.geometry.nlist,coarse_vector_bytes=self.geometry.centers.nbytes)
                        values=canonical(self.geometry.centers,q)
                        f.update(order=sorted(range(self.geometry.nlist),key=lambda j:(-float(values[j]),j)),
                            list_cursor=0,member_cursor=0,opened=[],target=target)
                        state.prepare_step='frontier'
                elif step=='frontier':
                    with clock.measure('membership'):
                        allowed=np.zeros(len(self.snap.ids),dtype=np.bool_);allowed[state.allowed]=True
                        ledger.charge(membership_bitmap_bytes=allowed.nbytes,membership_member_writes=len(state.allowed))
                    with clock.measure('posting'):
                        while len(state.positions)<f['target'] and f['list_cursor']<len(f['order']):
                            j=f['order'][f['list_cursor']];members=self.geometry.lists[j]
                            if j not in f['opened']:
                                ledger.charge(ivf_lists_opened=1);f['opened'].append(j)
                            if f['member_cursor']==len(members):f['list_cursor']+=1;f['member_cursor']=0;continue
                            ledger.charge(ivf_posting_checks=1,ivf_posting_bytes=8)
                            p=int(members[f['member_cursor']]);f['member_cursor']+=1
                            if allowed[p]:state.positions.append(p)
                            else:ledger.charge(ivf_out_of_scope_postings=1)
                        state.phase='score'
                elif step=='ann':
                    allowed=np.asarray(state.allowed,dtype=np.int64)
                    if len(allowed):
                        key=sha(allowed.tobytes())
                        if key not in self.ann:
                            with clock.measure('index_build'):
                                # Index construction has no query answer and is separately admitted.
                                self.ensure_ann(allowed,ledger)
                        with clock.measure('ann_search'):
                            ledger.charge(ann_calls=1)
                            found=self.ann[key].search(q.astype(np.float32),count=min(self.candidates,len(allowed)),threads=1)
                            ledger.charge(ann_distance_evaluations=int(found.computed_distances),ann_visited_members=int(found.visited_members))
                            state.positions=[int(x) for x in found.keys]
                    state.phase='score'
                else:raise ValueError('invalid preparation cursor')
            while state.phase=='score' and state.cursor<len(state.positions):
                if req.deadline_ms is not None and (time.perf_counter()-start)*1000>=req.deadline_ms:raise Exhausted('soft deadline')
                with clock.measure('score'):
                    n=min(64,len(state.positions)-state.cursor)
                    for key,per in [('canonical_scores',1),('vector_logical_bytes',self.store.dim*8)]:
                        remaining=ledger.limits.get(key,float('inf'))-ledger.consumed.get(key,0)
                        if np.isfinite(remaining):n=min(n,int(remaining//per))
                    if n<=0:raise Exhausted('canonical/vector budget')
                    batch=state.positions[state.cursor:state.cursor+n]
                    ledger.charge(canonical_scores=n,vector_logical_bytes=n*self.store.dim*8)
                    values=canonical(self.snap.vectors[batch],q)
                    state.scored.extend([[int(p),float(v)] for p,v in zip(batch,values)]);state.cursor+=n
            if state.phase=='score':
                with clock.measure('rank'):
                    state.selected=sorted(state.scored,key=lambda x:(-x[1],int(self.snap.ids[x[0]])))[:req.k]
                    f.update(scored_count=len(state.scored),termination='exhaustive' if len(state.scored)==f['eligible'] else 'fixed_approximate')
                    state.phase='sources'
            while state.phase=='sources' and len(state.sources)<len(state.selected):
                with clock.measure('source_fetch'):
                    p,value=state.selected[len(state.sources)];row=self.snap.rows[p]
                    ledger.charge(source_reads=1,source_logical_bytes=len(row['text'].encode()),materialized_text_checks=1)
                    if not row['visible'] or not row['path'].replace('\\','/').startswith(prefix) or sha(row['text'].encode())!=row['content_sha']:
                        raise ValueError('invalid source or legal scope')
                    state.sources.append(dict(id=int(self.snap.ids[p]),version=row['version'],score=value,path=row['path'],
                        content_sha=row['content_sha'],provenance=row['provenance'],text=row['text'],
                        source_verification=dict(snapshot_content=True,original_file=False)))
            if state.phase=='sources':state.phase='commit'
            if state.phase=='commit':
                with clock.measure('commit'):
                    # Same compact completion layout, even if one backend scored more vectors.
                    state.positions=[];state.scored=[];state.allowed=[]
                    for key in ['order','opened','list_cursor','member_cursor']:f.pop(key,None)
                    self.store.save(state,ledger);state.phase='done'
            return Result(ResultKind.APPROXIMATE,self.snap.identity,SCORE,state.sources,
                dict(strict_certificate=False,semantic_quality='unreviewed',eligible=f['eligible'],termination=f['termination'],
                     ann_resident_bytes=sum(int(i.memory_usage) for i in self.ann.values())),clock.resources(ledger,start))
        except Exhausted as exc:
            state.consumed=ledger.consumed.copy()
            return Result(ResultKind.PENDING,self.snap.identity,SCORE,[],
                dict(scope_status='known' if state.request_data['scope_known'] else 'unknown',strict_certificate=False),
                clock.resources(ledger,start),state,str(exc))
        except (ValueError,TypeError) as exc:
            return Result(ResultKind.REJECTED,self.snap.identity,SCORE,[],{},clock.resources(ledger,start),reason=str(exc))
