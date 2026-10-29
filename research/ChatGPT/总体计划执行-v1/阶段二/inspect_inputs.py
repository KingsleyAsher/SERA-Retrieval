from pathlib import Path
import sqlite3, json, inspect
import numpy as np
from usearch.index import Index

ROOT = Path(__file__).resolve().parents[3]
p = ROOT / '.private-kb-experiments/plan-v1-stage1'
db = sqlite3.connect((p/'frozen.sqlite').as_uri()+'?mode=ro', uri=True)
print('tables', db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
for name in ('docs', 'chunks', 'meta'):
    print(name, db.execute(f'PRAGMA table_info({name})').fetchall())
print('meta', dict(db.execute('SELECT key,value FROM meta')))
print('vector', np.load(p/'vectors.npy', mmap_mode='r').shape)
print('private_files', [x.name for x in (ROOT/'.private-kb-experiments').iterdir()])
cache = sqlite3.connect((ROOT/'.private-kb-experiments/embedding-cache.sqlite').as_uri()+'?mode=ro', uri=True)
print('embedding_schema', cache.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall())
print('index_search_signature', inspect.signature(Index.search))
index = Index(ndim=2, metric='cos', dtype='f32')
index.add(np.array([1,2]), np.array([[1,0],[0,1]], dtype=np.float32))
found = index.search(np.array([1,0], dtype=np.float32), count=1)
print('match_instrumentation', [x for x in dir(found) if not x.startswith('_')])
db.close(); cache.close()
