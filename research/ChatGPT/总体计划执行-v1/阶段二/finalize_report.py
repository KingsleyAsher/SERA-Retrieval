"""Summarize existing run without rerunning benchmarks or accessing test families."""
from pathlib import Path
import json, hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
result=json.loads((HERE/'results-summary.json').read_text(encoding='utf-8'))
raw=json.loads((ROOT/'.private-kb-experiments/plan-v1-stage2'/result['run']/'raw-results.json').read_text(encoding='utf-8'))
detail={}
for backend in ('full','ann','hybrid'):
    rows=[r for r in raw['requests'] if r['backend']==backend]
    detail[backend]={
        'first_request_seconds':rows[0]['resources']['seconds'],
        'snapshot_resident_payload_bytes':result['initialization']['snapshot_logical_bytes'],
        'index_resident_bytes':max(r['guarantee']['index_resident_bytes'] for r in rows),
        'updates':[r['resources'] for r in raw['updates'] if r['backend']==backend]
    }
result['cost_detail']=detail
result['request_counts']={'main':len(raw['requests']),'cache_requests':2*len(raw['cache']),
                          'filter':len(raw['filters']),'controlled_update':len(raw['updates'])}
result['canonical_read_reduction_only']=1-50/1213
result['warm_ann_total_reduction_vs_full']=1-result['aggregate'][1]['warm_total_ms']['mean']/result['aggregate'][0]['warm_total_ms']['mean']
(HERE/'results-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'request_counts':result['request_counts'],
    'cost_detail':{b:{'lexical_build_ms':r['first_request_seconds'].get('lexical_build',0)*1000,
                     'ann_build_ms':r['first_request_seconds'].get('ann_build',0)*1000,
                     'index_resident_bytes':r['index_resident_bytes']} for b,r in detail.items()},
    'warm_ann_reduction':result['warm_ann_total_reduction_vs_full'],
    'canonical_rerank_read_reduction':result['canonical_read_reduction_only']},ensure_ascii=False,indent=2))
