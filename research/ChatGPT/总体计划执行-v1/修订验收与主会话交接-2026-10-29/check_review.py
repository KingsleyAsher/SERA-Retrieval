"""Finite hand-calculation aids; no KB, embeddings, search or performance run."""
from pathlib import Path
import json,math,hashlib,re,importlib.util

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    sources=[ROOT/'WorkBuddy/独立审阅/02-组合界有限修订与诊断协议-2026-10-29.md',
             ROOT/'DeepSeek/本地Agent交付/06-热启动候选有限修订-2026-10-29.md']
    manifest=[]
    for i,p in enumerate(sources,1):
        b=p.read_bytes();t=b.decode('utf-8-sig');dest=HERE/f'input-{i}.md'
        if dest.exists():assert dest.read_bytes()==b,'preserve prior audit; use new folder'
        else:dest.write_bytes(b)
        pat=re.compile(r'实测|\d+(?:\.\d+)?\s*[%％]|显著|恒|恰等|前二十|不是完成')
        manifest.append(dict(source=str(p),copy=dest.name,bytes=len(b),lines=len(t.splitlines()),
            sha256=hashlib.sha256(b).hexdigest(),risk_hits=[dict(line=n,text=x) for n,x in enumerate(t.splitlines(),1) if pat.search(x)]))
    # Reuse only the preceding review's pure arithmetic helper.
    spec=importlib.util.spec_from_file_location('prior_math',ROOT/'ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/check_math.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    checks=[]
    def record(name,**details):checks.append(dict(name=name,**details))
    A=mod.bounds([[7/25,0,24/25],[-7/25,0,24/25],[0,7/25,24/25],[0,-7/25,24/25]],[2/3,2/3,1/3])
    assert A['sphere']>.70>=A['stat'] and A['actual_min_squared']>.70
    record('WB_sphere_only_success_example',**A)
    B=mod.bounds([[0.,1.],[0.,-1.]],[1.,0.])
    assert B['stat']>1 and B['sphere']==0
    record('WB_stat_only_success_example',**B)
    F=mod.bounds([[1.,0.],[-1.,0.],[0.,1.],[0.,-1.]],[.2,.2])
    assert F['sphere']==F['stat']==0 and abs(F['actual_min_squared']-.68)<1e-14
    record('WB_nonunit_query_failure_example_is_valid_under_contract_A',**F)

    # Literal S1 schedule: partition marked visited, then a partial scan hits budget.
    partition=[.6,.95];P=[.5];visited={0};P.append(partition[0]);cursor=1
    ub_after_restore=[] if 0 in visited else [.95]
    assert not ub_after_restore and max(P)<max(partition)
    record('DS_partial_partition_cannot_be_marked_completed',returned=max(P),missed=partition[cursor],
           required_state=['active_partition','member_cursor','completed_partitions'])

    # Old filter upper bound need not cover newly eligible items.
    old_members=[-1.];new_members=[-1.,1.];old_upper=-1.
    assert old_upper<max(new_members)
    record('DS_scope_expansion_requires_bound_coverage_not_just_legal_support',old_upper=old_upper,new_max=max(new_members))

    # Both queries and members are unit; the permitted arbitrary center has norm>beta.
    q0=[-.8,.6];q=[-.6,.8];c=[2.,0.];rho=1.;beta=1.
    delta=mod.norm(mod.sub(q,q0));U0=mod.dot(q0,c)+rho
    transferred=U0+beta*delta;fresh=mod.dot(q,c)+rho;actual=mod.dot(q,[1.,0.])
    assert actual<=transferred<fresh
    record('DS_transferred_bound_not_always_looser_than_fresh_ball_bound',
           delta=delta,transferred=transferred,fresh=fresh,actual=actual,center_norm=2.,beta=beta)

    # Stored FP32 vectors can have different lengths, so cosine and L2 rank can differ.
    q=[1.,0.];x=[2.,0.];y=[1.,.125]
    cosx=mod.dot(q,x)/(mod.norm(q)*mod.norm(x));cosy=mod.dot(q,y)/(mod.norm(q)*mod.norm(y))
    dx=mod.dot(mod.sub(q,x),mod.sub(q,x));dy=mod.dot(mod.sub(q,y),mod.sub(q,y))
    assert cosx>cosy and dx>dy
    record('WB_unit_cosine_mapping_cannot_be_general_FP32_L2_contract',cosine_x=cosx,cosine_y=cosy,L2_x=dx,L2_y=dy)

    K=10;scope_count=3;returned=3
    assert scope_count<K and returned==scope_count
    record('DS_exhaustive_short_scope_can_complete',K=K,eligible=scope_count,returned=returned)
    out=dict(check_count=len(checks),checks=checks,scope='constructed arithmetic and literal pseudocode-state examples; not executable backend tests or performance evidence')
    for name,obj in [('inputs.json',manifest),('checks.json',out)]:
        (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(files=len(manifest),bytes=sum(x['bytes'] for x in manifest),
        lines=sum(x['lines'] for x in manifest),checks=len(checks),risk_lines=[len(x['risk_hits']) for x in manifest],
        inputs=[{k:v for k,v in x.items() if k!='risk_hits'} for x in manifest]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
