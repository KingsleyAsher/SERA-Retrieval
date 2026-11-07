"""Allowlisted aggregate-only publication from private offline diagnostics."""
import argparse
import json
import statistics
from pathlib import Path

from research.reuse_foundation.common import digest
from research.reuse_foundation.runtime import atomic_publish


def summarize(source):
    raw=Path(source).read_bytes()
    data=json.loads(raw)
    cases=data['cases']
    assert len(cases)==128 and data['actual_128_cases_executed']
    assert {(c['query_index'],c['nlist'],c['C']) for c in cases}=={
        (q,n,C) for q in range(48) if q%3 for n in (16,64) for C in (50,200)}
    assert all(c['denominator']==1213 and c['paid_threshold'] is not None for c in cases)
    configurations=[]
    for nl in (16,64):
        for C in (50,200):
            selected=[c for c in cases if c['nlist']==nl and c['C']==C]
            bound_names=('ball','sphere','stat','combined','transfer')
            configs=dict(nlist=nl,C=C,different_rewrites=32,
                unique_unscored_excludable={name:dict(mean=statistics.mean(c['unique_unscored_excludable'][name] for c in selected),
                    maximum=max(c['unique_unscored_excludable'][name] for c in selected),
                    rewrites_at_least_20_percent=sum(c['unique_unscored_excludable'][name]/1213>=.2 for c in selected)) for name in bound_names},
                oracle_combined_excludable_maximum=max(sum(b['oracle_excludable'] for b in c['blocks']) for c in selected),
                minimum_combined_bound_minus_paid_threshold=min(b['observed']['combined']-c['paid_threshold'] for c in selected for b in c['blocks']),
                planning_median_ms=statistics.median(c['planning_seconds']*1000 for c in selected),
                support_median_ms=statistics.median(c['support_seconds']*1000 for c in selected),
                evaluation_median_ms=statistics.median(c['evaluation_seconds']*1000 for c in selected),
                matching_median_ms=statistics.median(c['matching_seconds']*1000 for c in selected),
                current_support_scores_per_case=C,current_support_vector_bytes_per_case=C*1024*8,
                matching_scores_per_case=16,matching_vector_bytes_per_case=16*1024*8,
                oracle_scores_per_case=1213,oracle_vector_bytes_per_case=1213*1024*8,
                l2_reference_vectors_per_case=1213,l2_reference_vector_bytes_per_case=1213*1024*8,
                old_support_scores_per_case=C,
                categories={name:sum(c['categories'][name] for c in selected) for name in ('sphere_only','stat_only','both','neither')})
            configurations.append(configs)
    return dict(format=1,dataset=dict(chunks=1213,revision=1216,dimension=1024,anchors=16,different_rewrites=32,semantic_labels='unreviewed'),
        actual_diagnostic_cases=128,independent_query_count=32,block_comparisons=sum(len(c['blocks']) for c in cases),
        raw_numerical_coverage_violations=data['numerical_violations'],configurations=configurations,
        layouts=[dict(nlist=l['nlist'],build_seconds=l['seconds'],statistics_payload_bytes=l['statistics']['payload_bytes'],
                      partition_sha=l['partition_sha'],statistics_sha=l['statistics_sha'],resources=l['resources']) for l in data['layouts']],
        anchor_fills=[dict(C=f['C'],seconds=f['seconds'],resources=f['resources'],index_sha256=f['index_sha256']) for f in data['ann_fill']],
        private_result_sha256=digest(raw),screening_rule_status='draft_not_used_as_acceptance',
        outcome='no_observed_pruning_potential_at_fixed_configurations',online_stopping=False,
        strict_certificate=False,maintenance_cost_measured=False,
        limitations=['ordinary float64 observations, not numerical certification',
            'only aggregate publication; original texts, query vectors and block tables stay private',
            'planning timing includes Python payload serialization accounting; not an optimized bound kernel',
            'evaluation work and old-bound construction are separate from current-query constructible work',
            'matching computed once per query/layout and physically shared across C in this replay; per-case counts describe standalone arms',
            'one frozen development corpus, no semantic labels or speed benefit claim'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();atomic_publish(args.output,summarize(args.input))
