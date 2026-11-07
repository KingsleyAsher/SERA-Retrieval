"""Publish aggregate opportunity ceilings, never a synthetic natural hit rate."""
import argparse
import json
import statistics
from pathlib import Path

from research.reuse_foundation.common import digest
from research.reuse_foundation.runtime import atomic_publish


def break_even(lookup, saved, fill=0., uses=None, maintenance=None):
    if min(lookup,saved,fill)<0:raise ValueError('costs must be nonnegative')
    if uses is not None and uses<=0:raise ValueError('positive amortization count required')
    optimistic=lookup/saved if saved else None
    return dict(lookup_only_required_valid_hit_probability=optimistic,
                actual_required_valid_hit_probability=None if not saved or uses is None or maintenance is None else (lookup+fill/uses+maintenance)/saved,
                measured_natural_valid_hit_probability=None)


def analyze(measurement,card,packet,review):
    review_path=Path(review)
    data=json.loads(Path(measurement).read_text());card=json.loads(Path(card).read_text())
    raw=Path(packet).read_bytes();packet=json.loads(raw);review=json.loads(Path(review).read_text())
    if review['packet_sha256']!=digest(raw) or review['user_accepted'] or review['gold'] or review['judgment_pool_complete']:
        raise ValueError('review must be a bound provisional incomplete pool')
    expected={}
    for group in packet['packets']:
        for v,q in enumerate(group['queries']):
            for c in group['candidates']:
                expected[group['family']*3+v,c['id']]=(digest(q),c['content_sha'],c['version'])
    labels=review['judgments']
    if len(labels)!=96 or len({(j['query_index'],j['chunk_id']) for j in labels})!=96:raise ValueError('incomplete or duplicate review')
    for j in labels:
        if j['grade'] not in (0,1,2) or expected.get((j['query_index'],j['chunk_id']))!=(j['query_sha256'],j['content_sha256'],j['version']):
            raise ValueError('review identity/hash/grade mismatch')
    rows=data['measurements'];pairs=data['cache_pairs']
    if len(rows)!=432 or len(pairs)!=144 or data['natural_trace']:raise ValueError('unexpected controlled measurement design')
    if len({(r['rep'],r['query'],r['backend']) for r in rows})!=432:raise ValueError('duplicate measurements')
    matching_median=statistics.median(r['seconds'] for r in data['matching'])
    backends=[]
    for backend in ('full','ann','hybrid'):
        selected=[r for r in rows if r['backend']==backend]
        chosen=[p for p in pairs if p['backend']==backend]
        totals=[r['resources']['seconds']['total'] for r in selected]
        def component(r,name):return r['resources']['seconds'].get(name,0.)
        components={name:dict(median_ms=statistics.median(component(r,name)*1000 for r in selected),
            median_removal_ceiling_fraction=statistics.median(component(r,name)/component(r,'total') for r in selected))
            for name in ('canonical_score','source_fetch','state_commit','rank','ann_search','lexical_search')}
        # prepare contains ANN/lexical child times. It is never added to them.
        for r in selected:
            t=r['resources']['seconds']
            accounted=sum(t.get(n,0) for n in ('prepare','canonical_score','rank','source_fetch','state_commit'))
            if accounted>t['total']+1e-9:raise ValueError('overlapping component accounting')
        for p in chosen:
            if p['miss']['cache_hit'] or not p['hit']['cache_hit'] or p['miss']['ids']!=p['hit']['ids']:
                raise ValueError('invalid controlled cache pair')
            c=p['hit']['resources']['consumed']
            if c.get('canonical_scores',0)!=0 or c.get('source_reads')!=10 or c.get('state_commits')!=1:
                raise ValueError('ordinary cache bypasses source/commit contract')
        source_median=statistics.median(component(r,'source_fetch') for r in selected)
        score_median=statistics.median(component(r,'canonical_score') for r in selected)
        backends.append(dict(backend=backend,queries=48,repetitions=3,total_median_ms=statistics.median(totals)*1000,
            components=components,matching_lookup_median_ms=matching_median*1000,
            optimistic_source_only_break_even=break_even(matching_median,source_median),
            optimistic_scoring_only_break_even=break_even(matching_median,score_median),
            controlled_cache_miss_median_ms=statistics.median(p['miss']['resources']['seconds']['total'] for p in chosen)*1000,
            controlled_cache_hit_median_ms=statistics.median(p['hit']['resources']['seconds']['total'] for p in chosen)*1000,
            natural_hit_rate=None,initialization_and_prewarm=data['warmup'][backend]['resources']))
    reviewed_queries={j['query_index'] for j in labels}
    qdirect=sum(any(j['grade']==2 for j in labels if j['query_index']==q) for q in reviewed_queries)
    qnone=sum(all(j['grade']==0 for j in labels if j['query_index']==q) for q in reviewed_queries)
    return dict(format=1,workload=card,initialization=data.get('initialization',{}),measurement_count=len(rows),controlled_cache_pairs=len(pairs),
        semantic_review=dict(status='assistant_reviewed_provisional',questions=48,judgments=96,
            pool='anchor full-canonical top two, reused as a fixed evidence pool for its three wordings',
            grade_counts={str(g):sum(j['grade']==g for j in labels) for g in (0,1,2)},
            questions_with_direct_evidence_in_reviewed_pair=qdirect,questions_with_only_zero_grades_in_reviewed_pair=qnone,
            user_accepted=False,judgment_pool_complete=False,formal_ndcg_at_10=None,formal_pooled_recall_at_10=None,
            answerability=None,temporal_authority_verified=False),
        backends=backends,private_measurement_sha256=digest(Path(measurement).read_bytes()),private_review_sha256=digest(review_path.read_bytes()),
        protocol_sha256=card['protocol_sha'],decision='no_new_mechanism_selected_pending_natural_workload_and_quality_evidence',
        limitations=['authored queries are not a natural traffic trace',
            'journal has no timestamp, operation type or before/after payload; natural update replay unavailable',
            'timing repetitions are not independent workloads',
            'component removal ceilings assume zero replacement overhead; not attainable architecture gains',
            'prepare includes ANN and lexical child spans; never sum parent and children',
            'source timing measures materialized snapshot hash validation, not original-file I/O',
            'ordinary exact-request cache is a baseline facility, not a SERA contribution',
            'lookup-only break-even omits fill, invalidation, candidate reads and semantic validation',
            'no global semantic metrics or quality-matched speed claim'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--private-run',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.private_run)
    result=analyze(root/'measurements.json',root/'data-card.json',root/'review-packet.json',root/'reviewed-labels.json')
    atomic_publish(args.output,result)
