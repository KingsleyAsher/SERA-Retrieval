"""Select one directory using metadata only, before reading query outcomes."""
from pathlib import Path
import json, sqlite3, hashlib
from collections import defaultdict
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
PRIVATE=None  # explicit isolated fixture directory required

def main():
    if PRIVATE is None: raise RuntimeError('explicit fixture directory required')
    destination=PRIVATE/'plan-v1-stage3-scope'
    destination.mkdir(exist_ok=True)
    path=destination/'scope-selection.json'
    if path.exists():raise ValueError('scope already selected; do not choose again after observing results')
    frozen=PRIVATE/'plan-v1-stage1/frozen.sqlite'
    db=sqlite3.connect(frozen.as_uri()+'?mode=ro',uri=True)
    rows=db.execute('SELECT d.id,d.visible,c.path FROM docs d JOIN chunks c ON c.id=d.id ORDER BY d.id').fetchall();db.close()
    groups=defaultdict(list)
    total=sum(bool(v) for _,v,_ in rows)
    for ident,visible,p in rows:
        if not visible:continue
        p=p.replace('\\','/')
        for i,ch in enumerate(p):
            if ch=='/':groups[p[:i+1]].append(ident)
    options=[(p,ids) for p,ids in groups.items() if max(10,total//10)<=len(ids)<=total*.75]
    if not options:raise ValueError('no nontrivial eligible directory; report missing scope rather than invent one')
    prefix,ids=min(options,key=lambda x:(abs(len(x[1])-total/2),x[0]))
    result=dict(date='2026-10-30',selector='eligible directory nearest half visible corpus; Unicode lexicographic tie; no query relevance/results',
        source_prefix=prefix,eligible_ids=ids,eligible_count=len(ids),total_visible=total,
        scope_sha256=hashlib.sha256(prefix.encode()).hexdigest(),scope_type='canonical trailing-separator directory prefix',
        candidate_directories=len(options),revision=1216)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['selector','eligible_count','total_visible','scope_sha256','candidate_directories']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
