"""Explicit offline 128-case replay. Requires excluded frozen assets; no API client."""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from usearch.index import Index

from research.reuse_foundation.common import Ledger, canonical, digest, packed, framework
from research.reuse_foundation.runtime import atomic_publish
from .diagnostics import build_statistics, diagnose, input_availability


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,help='new private directory outside the repository')
    parser.add_argument('--inputs-root',help='explicit external directory with .private-kb-experiments and ChatGPT')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    availability=input_availability(root,args.inputs_root)
    if availability['missing']:
        print(packed(availability)); return 2
    output=Path(args.output).resolve()
    if output.is_relative_to(root) or output.exists():
        raise ValueError('private output must be a new directory outside the repository')
    original=root/'research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF'
    sys.path.insert(0,str(original))
    spec=importlib.util.spec_from_file_location('_stage32_private_inputs',original/'run_experiment.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    if args.inputs_root:
        module.ROOT=Path(args.inputs_root).resolve()
        module.PRIVATE=module.ROOT/'.private-kb-experiments'
    records,queries,texts,namespace,manifest,load=module.load_inputs()
    if manifest['snapshot_revision'] != 1216 or len(set(texts)) != 48:
        raise ValueError('frozen revision or unique query count mismatch')
    x=np.stack([r['vector'] for r in records]); queries=np.asarray(queries)
    if x.shape!=(1213,1024) or queries.shape!=(48,1024) or not all(r['visible'] for r in records):
        raise ValueError('frozen dataset shape or main-scope visibility mismatch')
    for q in queries: framework.valid_vector(q,1024)
    output.mkdir(parents=True)
    atomic_publish(output/'inputs.json',dict(load=load,namespace=namespace,source_manifest=manifest,
        vector_sha=digest(x.tobytes()),query_vector_sha=digest(queries.tobytes()),
        protocol_sha=digest((root/'research/ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/protocol.json').read_bytes())))
    pools={}; fill=[]
    for C in (50,200):
        ledger=Ledger(); ledger.charge(index_builds=1,index_input_vector_bytes=len(x)*1024*4)
        started=time.perf_counter()
        index=Index(ndim=1024,metric='cos',dtype='f32',connectivity=16,expansion_add=128,expansion_search=128)
        index.add(np.arange(len(x),dtype=np.uint64),x.astype(np.float32),threads=1)
        for a in range(16):
            ledger.charge(ann_calls=1)
            result=index.search(queries[3*a].astype(np.float32),count=C,threads=1)
            pools[C,a]=list(map(int,result.keys))
            ledger.charge(observed_ann_distances=int(result.computed_distances),observed_ann_visits=int(result.visited_members))
        index.save(str(output/f'anchors-C{C}.usearch'))
        fill.append(dict(C=C,seconds=time.perf_counter()-started,resources=ledger.dump(),
                         index_sha256=digest((output/f'anchors-C{C}.usearch').read_bytes())))
    anchor_vectors=queries[::3]
    cases=[]; layouts=[]
    for nlist in (16,64):
        started=time.perf_counter()
        assignment=KMeans(n_clusters=nlist,n_init=1,random_state=20261029,max_iter=50,tol=1e-4,algorithm='lloyd').fit(x)
        lists=[np.flatnonzero(assignment.labels_==j).tolist() for j in range(nlist)]
        centers=assignment.cluster_centers_
        stats_ledger=Ledger(); stats,build=build_statistics(x,lists,centers,stats_ledger)
        np.savez(output/f'partition-{nlist}.npz',assignment=assignment.labels_,centers=centers,
                 posting_offsets=np.cumsum([0]+[len(m) for m in lists]),postings=np.concatenate(lists))
        atomic_publish(output/f'stats-{nlist}.json',stats)
        layouts.append(dict(nlist=nlist,seconds=time.perf_counter()-started,statistics=build,
            resources=stats_ledger.dump(),input_vector_bytes=x.nbytes,
            partition_sha=digest((output/f'partition-{nlist}.npz').read_bytes()),
            statistics_sha=digest(packed(stats))))
        for qi in range(48):
            if qi%3==0: continue
            match_ledger=Ledger(); match_ledger.charge(anchor_match_scores=16,anchor_vector_bytes=anchor_vectors.nbytes)
            match_started=time.perf_counter()
            values=canonical(anchor_vectors,queries[qi])
            eligible=[a for a in range(16) if digest(queries[3*a].tobytes())!=digest(queries[qi].tobytes())]
            if not eligible: raise ValueError('no compatible old anchor')
            a=min(eligible,key=lambda a:(-float(values[a]),a))
            match_seconds=time.perf_counter()-match_started
            for C in (50,200):
                data=diagnose(x,queries[qi],queries[3*a],stats,pools[C,a],k=10)
                cases.append(dict(query_index=qi,matched_anchor=a,nlist=nlist,C=C,
                                  matching=match_ledger.dump(),matching_seconds=match_seconds,**data))
    if len(cases)!=128: raise AssertionError('expected 128 fixed diagnostic cases')
    atomic_publish(output/'diagnostics.json',dict(cases=cases,layouts=layouts,ann_fill=fill,
        actual_128_cases_executed=True,strict_certificate=False,online_pruning=False,
        numerical_violations=sum(len(c['raw_coverage_violations']) for c in cases),
        maintenance_cost_measured=False,screening_decision=None,
        old_bound_cost_note='Old-bound construction/reference work remains in evaluation ledgers; transfer is an offline comparison, not a free online facility.'))
    print(packed(dict(cases=len(cases),private_output=str(output),online_pruning=False)))
    return 0


if __name__=='__main__': sys.exit(main())
