"""Read-only adapters. KB texts/policy must be explicitly exported, never guessed."""
import json
import sqlite3
from pathlib import Path

import numpy as np

from .common import digest, packed

STATES = {'active', 'pending', 'withdrawn', 'superseded', 'deleted'}


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _stamp(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _slice(text, start, end):
    # Plugin offsets are JavaScript UTF-16 code units, not Python code points.
    if type(start) is not int or type(end) is not int or start < 0 or end < start:
        raise ValueError('invalid UTF-16 chunk range')
    raw = text.encode('utf-16-le')
    if end * 2 > len(raw):
        raise ValueError('chunk outside source')
    return raw[start * 2:end * 2].decode('utf-16-le')


def _knowledge(directory):
    directory = Path(directory).resolve(strict=True)
    observed = {}
    file_hashes = {}

    def read(name):
        p = directory / name
        if p.is_symlink() or p.resolve().parent != directory:
            raise ValueError('source bundle must contain regular local files')
        observed[p] = _stamp(p)
        raw = p.read_bytes()
        file_hashes[name] = digest(raw)
        return json.loads(raw)

    manifest, catalog, mapping = read('manifest.json'), read('catalog.json'), read('source-map.json')
    if manifest.get('format') != 1 or catalog.get('format') != 1 or mapping.get('format') != 1:
        raise ValueError('unsupported source format')
    model, preprocessing = mapping['model'], mapping['preprocessing']
    namespace, policy = mapping['namespace'], mapping['policy_revision']
    dimension, next_slot = manifest['dimension'], manifest['nextSlot']
    if type(dimension) is not int or not 1 <= dimension <= 65536 or type(next_slot) is not int or next_slot < 0:
        raise ValueError('invalid vector manifest')
    if not all(isinstance(v, str) and v for v in (model, preprocessing, namespace, policy)):
        raise ValueError('explicit namespace/model/preprocessing/policy required')
    records, seen_paths = [], set()
    for doc in catalog['documents']:
        path = doc['path']
        if path in seen_paths:
            raise ValueError('duplicate catalog path')
        seen_paths.add(path)
        source = mapping['documents'][path]
        text = source['text']
        if source['revision'] != doc['revision'] or source['content_sha'] != digest(text):
            raise ValueError('source text/revision integrity failure')
        if type(source['visible']) is not bool or source['status'] not in STATES:
            raise ValueError('explicit source visibility and lifecycle required')
        for chunk in doc['chunks']:
            body = _slice(text, chunk['start'], chunk['end'])
            prefix = chunk.get('inputPrefix', '')
            embedding_input = prefix + '\n\n' + body if prefix else body
            input_hash = digest(embedding_input)
            vector = None
            slot = manifest['vectors'].get(input_hash)
            raw_hash = None
            if slot is not None:
                if type(slot) is not int or not 0 <= slot < next_slot:
                    raise ValueError('invalid vector slot')
                shard = directory / f'vectors-{slot // 4096}.bin'
                if shard.is_symlink():
                    raise ValueError('vector symlink rejected')
                observed.setdefault(shard, _stamp(shard))
                with shard.open('rb') as f:
                    f.seek(slot % 4096 * dimension * 4)
                    raw = f.read(dimension * 4)
                raw_hash = digest(raw)
                if len(raw) != dimension * 4 or manifest.get('checksums', {}).get(str(slot)) != raw_hash:
                    raise ValueError('missing or invalid vector checksum')
                vector = np.frombuffer(raw, dtype='<f4').tolist()
            records.append(dict(namespace=namespace, id=f'{path}#{chunk["id"]}',
                version=str(doc['revision']), text=body, content_sha=digest(body),
                path=path, scope=source['scope'], visible=source['visible'], status=source['status'],
                policy_revision=policy, model=model, preprocessing=preprocessing,
                dimension=dimension, dtype='float32', vector=vector,
                provenance=dict(kind='knowledge', input_sha=input_hash, raw_vector_sha=raw_hash,
                                source_sha=source['content_sha'], start=chunk['start'], end=chunk['end'])))
    if any(_stamp(p) != old for p, old in observed.items()):
        raise ValueError('source bundle changed during export')
    return records, dict(kind='knowledge', namespace=namespace,
                        files=file_hashes)


def _memory(path):
    path = Path(path).resolve(strict=True)
    # mode=ro preserves SQLite WAL visibility; immutable=1 would skip live WAL.
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'plugin_memory_entries', 'controls', 'meta'} <= tables:
            raise ValueError('unsupported memory database')
        generation = db.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
        if not generation:
            raise ValueError('memory generation missing')
        namespace = 'memory:' + digest(str(path))[:24]
        records = []
        for entry in db.execute('SELECT * FROM plugin_memory_entries ORDER BY id'):
            e = dict(entry)
            control = db.execute('SELECT * FROM controls WHERE source_id=?', (e['source_id'],)).fetchone()
            if control is None and not e['detached']:
                raise ValueError('memory source controls missing')
            c = dict(control) if control else {}
            status = 'deleted' if e['deleted'] or c.get('deleted') else 'withdrawn' if c.get('withdrawn_at') is not None else 'active'
            if e.get('claim_id') and 'memory_claims' in tables:
                claim = db.execute('SELECT * FROM memory_claims WHERE id=?', (e['claim_id'],)).fetchone()
                if not claim and not e['detached']:
                    raise ValueError('memory claim missing')
                if claim and claim['valid_to'] is not None and status == 'active':
                    status = 'superseded'
                for table in ('pending_claim_changes', 'pending_reminder_changes', 'pending_operation_changes'):
                    if table in tables:
                        columns = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
                        where = ' AND resolved_at IS NULL' if 'resolved_at' in columns else ''
                        if db.execute(f'SELECT 1 FROM {table} WHERE target_id=?{where}', (e['claim_id'],)).fetchone() and status == 'active':
                            status = 'pending'
            text = e['body']
            proof = json.loads(e['proofs'])
            records.append(dict(namespace=namespace, id=e['id'], version=digest(packed(e)),
                text=text, content_sha=digest(text), path=e['id'],
                scope='global' if e['scope'] == 'global' else e['project'],
                visible=not bool(c.get('excluded') or c.get('deleted') or e['deleted']), status=status,
                policy_revision=str(generation[0]), model=None, preprocessing='memory-body-v1',
                dimension=None, dtype=None, vector=None,
                provenance=dict(kind='memory', source_id=e['source_id'], proofs=proof)))
        return records, dict(kind='memory', namespace=namespace, generation=str(generation[0]),
                             identity='resolved-path namespace; relocated copies are separate sources')
    finally:
        db.close()


def export_source(kind, path):
    if kind not in ('knowledge', 'memory'):
        raise ValueError('source kind must be knowledge or memory')
    records, manifest = _knowledge(path) if kind == 'knowledge' else _memory(path)
    return dict(format=1, records=records, source_manifest=manifest)
