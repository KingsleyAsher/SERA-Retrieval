"""JSON reference and binary resident candidate payloads with the same selector."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'阶段二'))
from framework import *

class CandidateBank:
    def __init__(self,layout='compact',capacity=16,max_bytes=4*1024*1024):
        self.layout,self.capacity,self.max_bytes=layout,capacity,max_bytes
        self.data=OrderedDict();self.bytes=0

    def put(self,bucket,q,items,origin,sequence,ledger):
        meta=dict(bucket=bucket,query_sha=sha(q.tobytes()),origin=origin,sequence=sequence)
        key=sha(packed([bucket,meta['query_sha'],sequence]).encode())
        seeds=np.asarray([[int(x['id']),int(x['version'])] for x in items],dtype=np.int64).reshape(-1,2)
        if self.layout=='json':
            item=packed(dict(meta,q=q.tolist(),seeds=seeds.tolist()))
            size=len(key.encode())+len(item.encode())
        else:
            v=np.asarray(q,dtype=np.float64).copy();v.flags.writeable=False;seeds.flags.writeable=False
            item=dict(meta=meta,q=v,seeds=seeds)
            size=len(key.encode())+len(packed(meta).encode())+v.nbytes+seeds.nbytes
        ledger.charge(candidate_writes=1,candidate_bytes_written=size)
        if size>self.max_bytes:raise ValueError('entry exceeds candidate cap')
        prior=self.data.pop(key,None)
        if prior:self.bytes-=prior[1]
        self.data[key]=(item,size);self.bytes+=size
        while len(self.data)>self.capacity or self.bytes>self.max_bytes:
            _,(_,oldsize)=self.data.popitem(last=False);self.bytes-=oldsize
        return key

    def match(self,bucket,q,ledger):
        ts=time.perf_counter();qsha=sha(q.tobytes())
        # Entire synchronous lookup is admitted atomically; no partial lookup is replayed.
        if self.layout=='json':
            ledger.charge(candidate_cache_lookups=1,candidate_entries_checked=len(self.data),
                          candidate_bytes_read=self.bytes)
            candidates=[]
            for key,(payload,_) in self.data.items():
                e=json.loads(payload)
                if e['bucket']==bucket and e['query_sha']!=qsha:
                    ledger.charge(candidate_match_scores=1)
                    value=float(canonical(np.asarray([e['q']],dtype=np.float64),q)[0])
                    candidates.append((-value,key,e))
            result=min(candidates,key=lambda x:(x[0],x[1])) if candidates else None
        else:
            # Same logical full-bank read policy as JSON. Binary matrices eliminate
            # decoding, not the declared scan. This is not a selected-payload oracle.
            ledger.charge(candidate_cache_lookups=1,candidate_entries_checked=len(self.data),
                          candidate_bytes_read=self.bytes)
            all_entries=list(self.data.items())
            all_vectors=np.stack([e['q'] for _,(e,_) in all_entries]) if all_entries else None
            all_seeds=[e['seeds'].copy() for _,(e,_) in all_entries]
            entries=[]
            for i,(key,(e,_)) in enumerate(all_entries):
                if e['meta']['bucket']==bucket and e['meta']['query_sha']!=qsha:entries.append((i,key,e))
            if entries:
                ledger.charge(candidate_match_scores=len(entries))
                # A small stack is explicit query-time work, included in measured matching.
                values=canonical(all_vectors[[i for i,_,_ in entries]],q)
                pick=min(range(len(entries)),key=lambda i:(-float(values[i]),entries[i][1]))
                i,key,e=entries[pick]
                result=(-float(values[pick]),key,dict(e['meta'],seeds=all_seeds[i].tolist()))
            else:result=None
        ledger.elapsed('candidate_match',ts)
        if result:
            _,key,e=result
            return dict(entry=key,seeds=e['seeds'],origin=e['origin'],origin_sequence=e['sequence'],
                        cursor=0,verified=0,stale=0,matched=True)
        return dict(entry=None,seeds=[],cursor=0,verified=0,stale=0,matched=False)

class IVF:
    """Controllable posting lists; no geometric pruning or certificate."""
    def __init__(self,snapshot,nlist):
        from sklearn.cluster import KMeans
        t=time.perf_counter();self.snapshot=snapshot.identity;self.nlist=nlist
        km=KMeans(n_clusters=nlist,n_init=1,random_state=20261029,max_iter=50,algorithm='lloyd')
        self.assignment=km.fit_predict(snapshot.vectors).astype(np.int64)
        self.centers=np.asarray(km.cluster_centers_,dtype=np.float64)
        self.lists=[np.flatnonzero(self.assignment==j).astype(np.int64) for j in range(nlist)]
        self.seconds=time.perf_counter()-t
        self.payload_bytes=self.assignment.nbytes+self.centers.nbytes+sum(x.nbytes for x in self.lists)
        self.list_sizes=[len(x) for x in self.lists]
