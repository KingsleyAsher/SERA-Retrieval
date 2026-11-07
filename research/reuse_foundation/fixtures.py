"""Reproducible invented inputs only; no plugin installation or model service."""
import json
import sqlite3
from pathlib import Path

import numpy as np

from .common import digest, packed

SEED = 20261107


def synthetic_records(count=128, dimension=1024):
    rng = np.random.default_rng(SEED)
    for i in range(count):
        v = rng.normal(size=dimension)
        v /= np.linalg.norm(v)
        text = f'Invented source {i}: constraint and evidence {i % 17}.'
        yield dict(namespace='synthetic', id=str(i), version='1', text=text,
            content_sha=digest(text), path=f'notes/{i}.md', scope='global', visible=True,
            status='active', policy_revision='1', model='synthetic-unit-v1',
            preprocessing='invented-v1', dimension=dimension, dtype='float64', vector=v,
            provenance=dict(synthetic=True, seed=SEED))


def knowledge_fixture(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    text = '# Invented\n😀 A synthetic condition.'
    end = len(text.encode('utf-16-le')) // 2
    prefix = 'Invented'
    embedding = prefix + '\n\n' + text
    vector = np.array([1, 2, 3, 4], dtype='<f4')
    vector /= np.linalg.norm(vector)
    raw = vector.tobytes()
    (root / 'vectors-0.bin').write_bytes(raw)
    catalog = dict(format=1, documents=[dict(path='invented.md', revision='r1',
        chunks=[dict(id=0, start=0, end=end, inputPrefix=prefix)])])
    mapping = dict(format=1, namespace='invented-kb', policy_revision='1',
        model='synthetic-unit-v1', preprocessing='structure-1:invented', documents={
            'invented.md': dict(text=text, revision='r1', content_sha=digest(text),
                                visible=True, status='active', scope='global')})
    manifest = dict(format=1, dimension=4, nextSlot=1, vectors={digest(embedding): 0},
                    checksums={'0': digest(raw)})
    for name, data in [('catalog.json', catalog), ('source-map.json', mapping), ('manifest.json', manifest)]:
        (root / name).write_text(packed(data), encoding='utf-8')
    return root


def memory_fixture(path):
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
      INSERT INTO meta VALUES('generation','1');
      CREATE TABLE controls(source_id TEXT PRIMARY KEY,excluded INTEGER,deleted INTEGER,withdrawn_at INTEGER);
      CREATE TABLE plugin_memory_entries(id TEXT PRIMARY KEY,source_id TEXT,claim_id TEXT,
        scope TEXT,project TEXT,title TEXT,body TEXT,quote TEXT,proofs TEXT,origin TEXT,
        detached INTEGER,deleted INTEGER,created REAL,metadata TEXT);
    ''')
    for i, scope in enumerate(('global', 'project')):
        text = f'Invented memory {i}.'
        db.execute('INSERT INTO controls VALUES(?,0,0,NULL)', (f's{i}',))
        db.execute('INSERT INTO plugin_memory_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (f'm{i}', f's{i}', None, scope, 'project:invented', 'Invented', text, text,
             json.dumps([dict(source_id=f's{i}', quote=text)]), 'manual', 1, 0, 0, '{}'))
    db.commit()
    db.close()
    return Path(path)
