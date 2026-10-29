"""Small mathematical counterexamples only; no KB, model, index or benchmark."""
from pathlib import Path
from fractions import Fraction
import json,math,hashlib,re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def sub(a,b):return [x-y for x,y in zip(a,b)]
def bounds(points,q):
    c=[sum(x[i] for x in points)/len(points) for i in range(len(q))]
    residuals=[sub(x,c) for x in points]
    rho=max(map(norm,residuals));t=[abs(x) for x in sub(q,c)]
    lo=[min(abs(x[i]) for x in residuals) for i in range(len(q))]
    hi=[max(abs(x[i]) for x in residuals) for i in range(len(q))]
    stat=sum(max(lo[i]-t[i],0,t[i]-hi[i])**2 for i in range(len(q)))
    sphere=max(norm(sub(q,c))-rho,0)**2
    return dict(sphere=sphere,stat=stat,centroid=c,radius=rho,
                actual_min_squared=min(dot(sub(q,x),sub(q,x)) for x in points))

def main():
    checks=[]
    def record(name,**data):checks.append(dict(name=name,**data))
    B=[[1.,0.],[-1.,0.]];q=[0.,1.];c=[0.,0.]
    actual=dot(sub(q,c),sub(q,c));wrong=2-2*dot(q,c)
    assert actual==1 and wrong==2
    record('unit_members_do_not_imply_unit_centroid',actual=actual,claimed_formula=wrong)

    a=[1.,0.];b=[0.,1.]
    assert (norm(a)-norm(b))**2==0 and dot(sub(a,b),sub(a,b))==2
    record('subspace_norm_difference_is_inequality_not_equality',norm_difference_squared=0,actual_squared=2)

    B=[[7/25,0,24/25],[-7/25,0,24/25],[0,7/25,24/25],[0,-7/25,24/25]]
    q=[2/3,2/3,1/3]
    assert all(abs(norm(x)-1)<1e-14 for x in B+[q])
    r=bounds(B,q);assert r['stat']<r['sphere']<=r['actual_min_squared']
    record('normalized_members_can_have_sphere_stronger_than_stat',**r)

    r=bounds([[0.,1.],[0.,-1.]],[1.,0.])
    assert r['sphere']==0 and r['stat']==2 and r['actual_min_squared']==2
    record('stat_can_also_be_stronger_than_sphere',**r)

    A=(0.,2.);B=(1.,3.);a=.5;b=1.5
    assert max(A[0],B[0])<=min(A[1],B[1]) and a!=b
    # Both orderings are compatible with these intervals, hence more information is needed.
    assert A[0]<=1.9<=A[1] and B[0]<=1.1<=B[1]
    record('overlap_with_distinct_true_values_does_not_invalidate_refinement',
           interval_A=A,interval_B=B,true_A=a,true_B=b,reverse_order_also_feasible=True)

    eps=Fraction(1,2**50);d1=Fraction(1);d2=Fraction(1)+eps*eps
    assert d1!=d2 and float(d1)==float(d2)
    record('exact_dyadic_distinguishes_float64_tie',extra_squared_distance='2^-100',float64_equal=True)

    oracle=.2;current_upper=.8;block_lower=.9
    assert current_upper>oracle and block_lower>current_upper
    record('valid_current_candidate_threshold_need_not_equal_oracle',oracle=oracle,current_threshold=current_upper,
           safe_block_lower=block_lower)

    q=[0.,1.];B=[[1.,0.],[-1.,0.]];r=bounds(B,q)
    assert r['sphere']==0 and r['actual_min_squared']==2>1
    record('normalized_shell_example_can_show_missed_pruning',**r,threshold=1)

    # S1: after visiting A, Q contains only B, while unseeded rest contains C.
    threshold=.8;u_Q=.7;u_rest=.99;true_rest=.95
    assert u_Q<threshold and max(u_Q,u_rest)>threshold and true_rest>threshold
    record('S1_Q_only_stop_can_miss_rest',threshold=threshold,Q_upper=u_Q,rest_upper=u_rest,rest_true=true_rest)

    q0=[1.,0.];q=[.88,math.sqrt(1-.88**2)]
    support=[.5,math.sqrt(.75)];tail=[-1.,0.]
    delta=norm(sub(q,q0));T0=dot(q0,support);U0=dot(q0,tail)
    assert delta>.45 and U0+delta<T0-delta
    assert dot(q,tail)<dot(q,support)
    record('S2_delta_above_point45_does_not_preclude_pruning',delta=delta,cosine=dot(q,q0),
           old_support_score=T0,old_tail_upper=U0,new_support_lower=T0-delta,new_tail_upper=U0+delta)

    # The support can be suboptimal in old q0, yet remains a valid threshold witness.
    assert dot(q0,q0)>T0 and dot(q,support)>=T0-delta
    record('S2_does_not_require_old_global_exact_topK',old_support_score=T0,old_better_score=1.,
           valid_new_lower=T0-delta)

    sources=[ROOT/'WorkBuddy/认证分支-球下界与子空间下界剪枝有效性分析-BGE-M3.md',
             ROOT/'DeepSeek/本地Agent交付/05-热启动候选方案-2026-10-29.md']
    risk=re.compile(r'\d+(?:\.\d+)?\s*[%％]|提升|领先|代际|实测|公开规格')
    manifest=[]
    for i,p in enumerate(sources,1):
        raw=p.read_bytes();text=raw.decode('utf-8-sig')
        copy=HERE/f'input-{i}.md'
        if copy.exists():assert copy.read_bytes()==raw,'preserve frozen input; use a new review directory'
        else:copy.write_bytes(raw)
        manifest.append(dict(source=str(p),copy=copy.name,bytes=len(raw),lines=len(text.splitlines()),
            sha256=hashlib.sha256(raw).hexdigest(),
            risk_hits=[dict(line=n,text=line) for n,line in enumerate(text.splitlines(),1) if risk.search(line)]))
    out=dict(check_count=len(checks),checks=checks,
        scope='small constructed real-arithmetic examples and one exact rational distinction; not machine certificates or benchmark gains')
    (HERE/'math-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (HERE/'inputs.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(checks=len(checks),sources=[{k:v for k,v in x.items() if k!='risk_hits'} for x in manifest],
        numeric_examples=checks[:4],risk_hit_counts=[len(x['risk_hits']) for x in manifest]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
