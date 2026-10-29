"""Metrics deliberately distinguish incomplete labels from established gold."""
import math

def evaluate(ranked,qrels,*,reviewed=False,judgment_pool_complete=False,k=10):
    if len(set(ranked))!=len(ranked):
        raise ValueError('duplicate result IDs')
    graded={int(i):int(g) for i,g in qrels.items()}
    if any(g not in (0,1,2) for g in graded.values()):
        raise ValueError('unsupported relevance grade')
    unknown=[i for i in ranked[:k] if i not in graded]
    formal=reviewed and judgment_pool_complete and not unknown
    # Missing labels are NOT silently turned into established irrelevant judgments.
    dcg=sum((2**graded.get(i,0)-1)/math.log2(pos+2) for pos,i in enumerate(ranked[:k]))
    ideal=sum((2**g-1)/math.log2(pos+2) for pos,g in enumerate(sorted(graded.values(),reverse=True)[:k]))
    relevant={i for i,g in graded.items() if g>0}
    return dict(status='reviewed_pooled_metrics' if formal else 'provisional_seed_diagnostic',
        ndcg_at_k=dcg/ideal if ideal and formal else None,
        pooled_recall_at_k=len(set(ranked[:k])&relevant)/len(relevant) if relevant and formal else None,
        seed_only_ndcg=dcg/ideal if ideal else None,
        unjudged_returned=len(unknown),
        answerability='not_evaluated_without_verified_answerability_labels')

def exact_neighbor_overlap(ranked,truth,k=10):
    return len(set(ranked[:k])&set(truth[:k]))/min(k,len(truth)) if truth else None
