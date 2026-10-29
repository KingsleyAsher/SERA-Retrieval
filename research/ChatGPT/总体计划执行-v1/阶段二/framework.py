"""Stage-two reference execution interfaces; isolated SQLite assets only.

No approximate-cache bypass, probability claim, strict certificate or API call.
All backends share canonical reranking, immutable snapshots, filters and LRU.
"""
import os
for _n in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_n] = '1'
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import OrderedDict, Counter
import hashlib, json, re, sqlite3, threading, time, uuid, datetime
import numpy as np
from usearch.index import Index

SCORE = 'normalized_ip_f64_v1'
HYBRID_SCORE = 'rrf60_dense50_lex50_v1'

def hybrid_contract(candidates):
    return f'rrf60_dense{candidates}_lex{candidates}_v1'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def canonical(vectors, query):
    return np.einsum('ij,j->i', vectors, query, optimize=False)

def valid_vector(vector, dim):
    v = np.asarray(vector, dtype=np.float64).copy()
    if v.shape != (dim,) or not np.isfinite(v).all() or abs(np.linalg.norm(v)-1) > 1e-8:
        raise ValueError('finite normalized vector required')
    return v

def tokens(text):
    out = re.findall(r'[a-z0-9_]+', text.lower())
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        out.extend(run)
        out.extend(run[i:i+2] for i in range(len(run)-1))
    # ASCII tokens prevent FTS parser syntax or segmentation ambiguity.
    return ['t'+x.encode('utf-8').hex() for x in out]

class ResultKind(str, Enum):
    APPROXIMATE = 'approximate'
    PROBABILISTIC = 'probabilistic'   # interface only; unavailable in stage two
    CERTIFIED = 'certified'           # interface only; unavailable in stage two
    PENDING = 'pending'
    REJECTED = 'rejected'

class Action(str, Enum):
    CANDIDATE_RESCORE = 'candidate_rescore'
    SEARCH_EXPAND = 'search_expand'
    BLOCK_SCAN = 'block_scan'
    EXACT_RERANK = 'canonical_rerank'
    SOURCE_FETCH = 'source_fetch'
    UPDATE_REPAIR = 'update_repair'

@dataclass(frozen=True)
class Scope:
    source_prefix: str = ''
    updated_on_or_before: str | None = None

@dataclass
class Request:
    vector: object
    backend: str = 'full'
    text: str = ''
    k: int = 10
    snapshot: str | None = None
    scope: Scope = field(default_factory=Scope)
    score_contract: str = SCORE
    quality: str = 'empirical'
    limits: dict = field(default_factory=dict)
    deadline_ms: float | None = None
    use_cache: bool = True

class Exhausted(Exception):
    pass

class Ledger:
    def __init__(self, limits=None, consumed=None):
        self.limits, self.consumed = dict(limits or {}), dict(consumed or {})
        self.reserved, self.times = {}, {}
        self.lock = threading.RLock()

    def charge(self, **units):
        # Synchronous reference: reserve all dimensions atomically, charge on issue.
        # No issued I/O cancellation refunds; no claim about physical disk bytes.
        with self.lock:
            for key, n in units.items():
                if n < 0 or self.consumed.get(key, 0)+self.reserved.get(key, 0)+n > self.limits.get(key, float('inf')):
                    raise Exhausted(key)
            for key, n in units.items():
                self.reserved[key] = self.reserved.get(key, 0)+n
            for key, n in units.items():
                self.reserved[key] -= n
                self.consumed[key] = self.consumed.get(key, 0)+n

    def elapsed(self, key, start):
        self.times[key] = self.times.get(key, 0.)+time.perf_counter()-start

    def dump(self):
        return dict(consumed=self.consumed.copy(), reserved=self.reserved.copy(),
                    limits=self.limits.copy(), seconds=self.times.copy(),
                    count_scope='cumulative_across_resume',time_scope='this_invocation_only')

@dataclass
class Execution:
    signature: str
    snapshot: str
    backend: str
    phase: str = 'prepare'
    cursor: int = 0
    positions: list = field(default_factory=list)
    scored: list = field(default_factory=list)
    lexical: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    consumed: dict = field(default_factory=dict)
    request_data: dict = field(default_factory=dict)
    prepare_step: str = 'lookup'
    allowed: list = field(default_factory=list)
    cache_hit: bool = False

@dataclass
class Result:
    kind: ResultKind
    snapshot: str
    score_contract: str
    items: list
    guarantee: dict
    resources: dict
    state: Execution | None = None
    reason: str = ''
    cache_hit: bool = False

@dataclass
class Snapshot:
    identity: str
    revision: int
    model: str
    ids: np.ndarray
    vectors: np.ndarray
    rows: list
    load_seconds: float
    logical_bytes: int
    owner: str = ''

    def allowed(self, scope):
        return np.array([i for i, r in enumerate(self.rows)
            if r['visible'] and r['path'].replace('\\', '/').startswith(scope.source_prefix.replace('\\', '/'))
            and (scope.updated_on_or_before is None or
                 (r['updated'] is not None and r['updated'] <= scope.updated_on_or_before))], dtype=np.int64)

class Store:
    """Committed revision catalog plus immutable version rows, single writer.

    Assets live inside SQLite; no external segment durability promise required.
    Snapshot objects own read-only materialized arrays and text for their epoch.
    """
    def __init__(self, path, dim, model):
        self.path, self.dim, self.model = Path(path), dim, model
        self.db = sqlite3.connect(path, isolation_level=None)
        prior_columns = [r[1] for r in self.db.execute('PRAGMA table_info(history)')]
        if prior_columns and 'content_sha' not in prior_columns:
            self.db.close()
            raise ValueError('legacy experimental schema; explicitly import into a new isolated store')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT);
          CREATE TABLE IF NOT EXISTS revisions(rev INTEGER PRIMARY KEY);
          CREATE TABLE IF NOT EXISTS history(id INTEGER,begin INTEGER,end INTEGER,version INTEGER,
             visible INTEGER,vector BLOB,text TEXT,path TEXT,updated TEXT,provenance TEXT,content_sha TEXT NOT NULL,
             PRIMARY KEY(id,begin));
          CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,digest TEXT,rev INTEGER);
          CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY,payload TEXT);
        ''')
        for k, v in [('dim', str(dim)), ('model', model), ('instance', str(uuid.uuid4()))]:
            self.db.execute('INSERT OR IGNORE INTO config VALUES(?,?)', (k, v))
        config = dict(self.db.execute('SELECT key,value FROM config'))
        if config['dim'] != str(dim) or config['model'] != model:
            raise ValueError('store namespace mismatch')
        self.instance = config['instance']
        # A copied database must not share cache/checkpoint ownership with its source.
        self.namespace = sha(packed([self.instance, os.path.normcase(str(self.path.resolve()))]).encode())

    def initialize(self, records, revision):
        if self.db.execute('SELECT count(*) FROM revisions').fetchone()[0]:
            raise ValueError('store already initialized')
        t = time.perf_counter()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for r in records:
                v = valid_vector(r['vector'], self.dim)
                self.db.execute('INSERT INTO history VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (int(r['id']), revision, None, r.get('version', revision), int(r.get('visible', True)),
                     v.tobytes(), r['text'], r['path'], r.get('updated'), packed(r.get('provenance', {})),sha(r['text'].encode())))
            self.db.execute('INSERT INTO revisions VALUES(?)', (revision,))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK'); raise
        return time.perf_counter()-t

    def latest(self):
        return self.db.execute('SELECT max(rev) FROM revisions').fetchone()[0]

    def snapshot(self, revision=None):
        t = time.perf_counter()
        self.db.execute('BEGIN')
        try:
            revision = self.latest() if revision is None else revision
            if self.db.execute('SELECT 1 FROM revisions WHERE rev=?', (revision,)).fetchone() is None:
                raise ValueError('unknown snapshot')
            records = self.db.execute('SELECT id,version,visible,vector,text,path,updated,provenance,content_sha FROM history '
                'WHERE begin<=? AND (end IS NULL OR end>?) ORDER BY id', (revision, revision)).fetchall()
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK'); raise
        ids = np.array([r[0] for r in records], dtype=np.int64)
        vectors = np.stack([np.frombuffer(r[3], dtype=np.float64) for r in records]) if records else np.empty((0, self.dim))
        rows = [dict(id=r[0], version=r[1], visible=bool(r[2]), text=r[4], path=r[5], updated=r[6],
                     provenance=json.loads(r[7]), content_sha=r[8]) for r in records]
        ids.flags.writeable = False; vectors.flags.writeable = False
        size = sum(len(r[3])+len(r[4].encode())+len(r[5].encode())+len(r[7].encode())+32 for r in records)
        digest = hashlib.sha256()
        for r in records:
            digest.update(packed([r[0],r[1],r[2],sha(r[3]),r[4],r[5],r[6],r[7],r[8]]).encode())
        return Snapshot(f'{self.namespace}:{revision}:{digest.hexdigest()}', revision, self.model, ids, vectors, rows,
                        time.perf_counter()-t, size, self.namespace)

    def mutate(self, operation_id, operations):
        # Validate before transaction; idempotent digest includes actual vector bytes.
        staged = []
        for op in operations:
            op = dict(op)
            if op['op'] not in ('put', 'delete'):
                raise ValueError('unknown operation')
            if op['op'] == 'put':
                op['vector'] = valid_vector(op['vector'], self.dim).tobytes().hex()
            staged.append(op)
        digest = sha(packed(staged).encode())
        t = time.perf_counter()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT digest,rev FROM operations WHERE id=?', (operation_id,)).fetchone()
            if old:
                if old[0] != digest:
                    raise ValueError('operation ID conflict')
                self.db.execute('ROLLBACK')
                return old[1], dict(idempotent=True, seconds=time.perf_counter()-t)
            rev = self.latest()+1
            if len({op['id'] for op in staged}) != len(staged):
                raise ValueError('duplicate IDs within batch')
            for op in staged:
                key = int(op['id'])
                self.db.execute('UPDATE history SET end=? WHERE id=? AND end IS NULL', (rev, key))
                if op['op'] == 'put':
                    self.db.execute('INSERT INTO history VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (key, rev, None, rev, int(op.get('visible', True)), bytes.fromhex(op['vector']),
                         op['text'], op['path'], op.get('updated'), packed(op.get('provenance', {})),sha(op['text'].encode())))
            self.db.execute('INSERT INTO revisions VALUES(?)', (rev,))
            self.db.execute('INSERT INTO operations VALUES(?,?,?)', (operation_id, digest, rev))
            self.db.execute('COMMIT')
            return rev, dict(idempotent=False, seconds=time.perf_counter()-t, operations=len(staged),
                             vector_write_bytes=sum(len(op.get('vector', ''))//2 for op in staged))
        except Exception:
            self.db.execute('ROLLBACK'); raise

    def save(self, state, ledger):
        # State lives in private SQLite, never in public reports.
        self.validate_state_owner(state)
        if any(ledger.consumed.get(key,0)<value for key,value in state.consumed.items()):
            raise ValueError('checkpoint ledger would erase previously consumed resources')
        ledger.charge(state_commits=1)
        state.consumed = ledger.consumed.copy()
        prior_bytes = ledger.consumed.get('state_payload_bytes', 0)
        # Fixed point includes its own byte-counter in the serialized checkpoint.
        for _ in range(8):
            payload = packed(asdict(state))
            total_bytes = prior_bytes + len(payload.encode())
            if state.consumed.get('state_payload_bytes') == total_bytes:
                break
            state.consumed['state_payload_bytes'] = total_bytes
        else:
            raise RuntimeError('checkpoint byte accounting did not converge')
        ledger.consumed = state.consumed.copy()
        t = time.perf_counter()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('INSERT OR REPLACE INTO executions VALUES(?,?)', (state.signature, payload))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK'); raise
        ledger.elapsed('state_commit', t)
        # measured bytes, not a physical WAL-byte or hard byte-limit claim
        return state.signature

    def restore(self, signature):
        row = self.db.execute('SELECT payload FROM executions WHERE id=?', (signature,)).fetchone()
        if row is None:
            raise ValueError('checkpoint missing')
        state = Execution(**json.loads(row[0]))
        self.validate_state_owner(state)
        return state

    def validate_state_owner(self, state):
        parts = state.snapshot.split(':')
        if len(parts)!=3 or parts[0]!=self.namespace or not parts[1].isdigit():
            raise ValueError('checkpoint belongs to another store')
        if self.db.execute('SELECT 1 FROM revisions WHERE rev=?',(int(parts[1]),)).fetchone() is None:
            raise ValueError('checkpoint snapshot unavailable')

    def close(self):
        self.db.close()

class ResultCache:
    def __init__(self, entries=32, max_bytes=4*1024*1024):
        self.entries, self.max_bytes, self.data = entries, max_bytes, OrderedDict()
        self.bytes = 0

    def get(self, identity):
        item = self.data.get(identity)
        if item is not None:
            self.data.move_to_end(identity)
            return json.loads(item)

    def put(self, identity, selected):
        payload = packed(selected)
        size = len(identity.encode())+len(payload.encode())
        if size > self.max_bytes:
            return
        old = self.data.pop(identity, None)
        if old is not None:
            self.bytes -= len(identity.encode())+len(old.encode())
        self.data[identity] = payload
        self.bytes += size
        while len(self.data) > self.entries or self.bytes > self.max_bytes:
            key, old = self.data.popitem(last=False)
            self.bytes -= len(key.encode())+len(old.encode())

class Engine:
    def __init__(self, store, snapshot, cache=None, candidates=50, ef=128):
        if snapshot.owner!=store.namespace or snapshot.model!=store.model or snapshot.vectors.shape!=(len(snapshot.ids),store.dim):
            raise ValueError('snapshot does not belong to this store/model/dimension')
        self.store, self.snap = store, snapshot
        self.cache = cache if cache is not None else ResultCache()
        self.candidates, self.ef = candidates, ef
        self.hybrid_score = hybrid_contract(candidates)
        self.ann = OrderedDict()
        self.fts = None
        self.initialization = []

    def ensure_ann(self, allowed, ledger, prepaid=False):
        key = sha(allowed.tobytes())
        if key not in self.ann:
            t = time.perf_counter()
            index = Index(ndim=self.store.dim, metric='cos', dtype='f32', connectivity=16,
                          expansion_add=128, expansion_search=self.ef)
            if not prepaid:
                ledger.charge(index_builds=1, index_input_vector_bytes=len(allowed)*self.store.dim*4)
            if len(allowed):
                index.add(allowed.astype(np.uint64), self.snap.vectors[allowed].astype(np.float32), threads=1)
            self.ann[key] = index
            ledger.elapsed('ann_build', t)
            self.initialization.append(dict(type='ann_build', n=len(allowed), seconds=time.perf_counter()-t))
            if len(self.ann) > 4:
                self.ann.popitem(last=False)
        self.ann.move_to_end(key)
        return self.ann[key]

    def lexical(self, text, allowed, ledger):
        query_terms = sorted(set(tokens(text)))[:128]
        admission = dict(lexical_queries=1,lexical_query_tokens=len(query_terms))
        if self.fts is None:
            admission.update(lexical_builds=1,lexical_build_input_bytes=sum(len(r['text'].encode()) for r in self.snap.rows))
        # Admit the whole synchronous lexical action before building or querying.
        ledger.charge(**admission)
        if self.fts is None:
            t = time.perf_counter()
            db = sqlite3.connect(':memory:')
            db.execute('CREATE VIRTUAL TABLE words USING fts5(body)')
            records = [(i, ' '.join(tokens(r['text']))) for i, r in enumerate(self.snap.rows)]
            db.executemany('INSERT INTO words(rowid,body) VALUES(?,?)', records)
            db.commit(); self.fts = db
            ledger.elapsed('lexical_build', t)
        if not query_terms:
            return []
        # All matching scores are considered before scope top50: no post-limit loss.
        rows = self.fts.execute('SELECT rowid,bm25(words) FROM words WHERE words MATCH ? ORDER BY bm25(words),rowid',
                               (' OR '.join(query_terms),)).fetchall()
        ledger.charge(lexical_matches=len(rows))
        permitted = set(allowed.tolist())
        return [int(i) for i, score in rows if i in permitted][:self.candidates]

    def run(self, req, state=None):
        start = time.perf_counter()
        contract = self.hybrid_score if req.backend == 'hybrid' else SCORE
        ledger = Ledger(req.limits, state.consumed if state else None)
        try:
            if req.backend not in ('full', 'ann', 'hybrid') or req.score_contract != contract:
                raise ValueError('backend / scoring contract mismatch')
            if req.quality != 'empirical':
                raise ValueError('probabilistic and strict guarantees unavailable in stage two')
            q = valid_vector(req.vector, self.store.dim)
            if req.k < 1 or (req.snapshot is not None and req.snapshot != self.snap.identity):
                raise ValueError('invalid K or snapshot')
            if req.snapshot is None and state is None and self.store.latest() != self.snap.revision:
                raise ValueError('stale executor: bind latest snapshot or explicitly request retained old snapshot')
            if req.backend != 'full' and req.k > self.candidates:
                raise ValueError('K exceeds configured approximate candidate pool')
            if req.scope.updated_on_or_before is not None:
                datetime.date.fromisoformat(req.scope.updated_on_or_before)
            supported = {'canonical_scores', 'vector_logical_bytes', 'metadata_checks', 'source_reads',
                'source_logical_bytes', 'materialized_text_checks', 'cache_lookups', 'result_cache_hits',
                'index_builds', 'index_input_vector_bytes', 'ann_calls', 'lexical_builds',
                'lexical_build_input_bytes', 'lexical_queries', 'lexical_query_tokens', 'state_commits'}
            if any(key not in supported or not isinstance(v, int) or v < 0 for key, v in req.limits.items()):
                raise ValueError('unsupported or invalid hard budget; observed ANN work cannot be capped mid-call')
            # Native calls cannot enforce a distance-count hard ceiling mid-search.
            if req.backend != 'full' and 'ann_distance_evaluations' in req.limits:
                raise ValueError('native ANN distance cap unsupported; choose resumable full backend')
            identity = sha(packed([self.snap.identity, self.snap.model, contract, req.backend,
                self.candidates, self.ef, asdict(req.scope), req.k, req.quality,
                sha(q.tobytes()), req.text if req.backend == 'hybrid' else '']).encode())
            if state is not None and (state.signature != identity or state.snapshot != self.snap.identity):
                raise ValueError('checkpoint request/snapshot mismatch')
            if state is not None and any(state.consumed.get(key, 0)>limit for key,limit in req.limits.items()):
                raise ValueError('resume limit is below already consumed resources')
        except (ValueError, TypeError) as exc:
            return Result(ResultKind.REJECTED, self.snap.identity, contract, [], {}, ledger.dump(), reason=str(exc))

        if state is None:
            state = Execution(identity, self.snap.identity, req.backend,
                request_data=dict(vector=q.tolist(), text=req.text, k=req.k, scope=asdict(req.scope),
                                  contract=contract, backend=req.backend))
        try:
            if state.phase == 'prepare':
                t = time.perf_counter()
                try:
                    while state.phase == 'prepare':
                        if state.prepare_step == 'lookup':
                            ledger.charge(cache_lookups=int(req.use_cache))
                            cached = self.cache.get(identity) if req.use_cache else None
                            if cached is not None:
                                state.selected, state.cache_hit = cached, True
                                state.prepare_step = 'cache_return'
                            else:
                                state.prepare_step = 'scope'
                        elif state.prepare_step == 'cache_return':
                            ledger.charge(result_cache_hits=1)
                            state.phase = 'sources'
                        elif state.prepare_step == 'scope':
                            ledger.charge(metadata_checks=len(self.snap.rows))
                            state.allowed = self.snap.allowed(req.scope).tolist()
                            if req.backend == 'full':
                                state.positions = state.allowed.copy()
                                state.phase = 'score'
                            else:
                                state.prepare_step = 'ann'
                        elif state.prepare_step == 'ann':
                            allowed = np.asarray(state.allowed,dtype=np.int64)
                            if len(allowed):
                                admission = dict(ann_calls=1)
                                if sha(allowed.tobytes()) not in self.ann:
                                    admission.update(index_builds=1,index_input_vector_bytes=len(allowed)*self.store.dim*4)
                                ledger.charge(**admission)
                                index = self.ensure_ann(allowed,ledger,prepaid=True)
                                ts = time.perf_counter()
                                found = index.search(q.astype(np.float32),count=min(self.candidates,len(allowed)),threads=1)
                                ledger.elapsed('ann_search',ts)
                                ledger.charge(ann_distance_evaluations=int(found.computed_distances),
                                              ann_visited_members=int(found.visited_members))
                                state.positions = [int(x) for x in found.keys]
                            state.actions.append(Action.SEARCH_EXPAND.value)
                            if req.backend=='hybrid' and len(allowed):
                                state.prepare_step = 'lexical'
                            else:
                                state.phase = 'score'
                        elif state.prepare_step == 'lexical':
                            ts = time.perf_counter()
                            state.lexical = self.lexical(req.text,np.asarray(state.allowed,dtype=np.int64),ledger)
                            ledger.elapsed('lexical_search',ts)
                            state.phase = 'score'
                        else:
                            raise ValueError('invalid prepare continuation')
                finally:
                    ledger.elapsed('prepare',t)

            while state.phase == 'score' and state.cursor < len(state.positions):
                if req.deadline_ms is not None and (time.perf_counter()-start)*1000 >= req.deadline_ms:
                    raise Exhausted('soft deadline')
                available = ledger.limits.get('canonical_scores', float('inf'))-ledger.consumed.get('canonical_scores', 0)
                n = int(min(64, len(state.positions)-state.cursor, available))
                if n <= 0:
                    raise Exhausted('canonical_scores')
                batch = state.positions[state.cursor:state.cursor+n]
                ledger.charge(canonical_scores=n, vector_logical_bytes=n*self.store.dim*8)
                ts = time.perf_counter()
                values = canonical(self.snap.vectors[batch], q)
                state.scored.extend([[int(p), float(v)] for p, v in zip(batch, values)])
                state.cursor += n
                ledger.elapsed('canonical_score', ts)
            if state.phase == 'score':
                ts = time.perf_counter()
                ranked = sorted(state.scored, key=lambda x: (-x[1], int(self.snap.ids[x[0]])))
                if req.backend == 'hybrid':
                    fused = Counter()
                    for channel in ([p for p, v in ranked], state.lexical):
                        for rank, p in enumerate(channel, 1):
                            fused[p] += 1/(60+rank)
                    ranked = sorted(fused.items(), key=lambda x: (-x[1], int(self.snap.ids[x[0]])))
                state.selected = [[int(p), float(v)] for p, v in ranked[:req.k]]
                state.actions.append((Action.BLOCK_SCAN if req.backend == 'full' else Action.EXACT_RERANK).value)
                state.phase = 'sources'
                ledger.elapsed('rank', ts)
            while state.phase == 'sources' and len(state.sources) < len(state.selected):
                p, score = state.selected[len(state.sources)]
                row = self.snap.rows[p]
                ledger.charge(source_reads=1, source_logical_bytes=len(row['text'].encode()), materialized_text_checks=1)
                ts = time.perf_counter()
                if not row['visible'] or sha(row['text'].encode()) != row['content_sha']:
                    raise ValueError('invalid source in pinned snapshot')
                state.sources.append(dict(id=int(self.snap.ids[p]), version=row['version'], score=score,
                    path=row['path'], content_sha=row['content_sha'], provenance=row['provenance'], text=row['text'],
                    source_verification=dict(snapshot_content=True,original_file=False)))
                ledger.elapsed('source_fetch', ts)
            if state.phase == 'sources':
                state.actions.append(Action.SOURCE_FETCH.value)
                state.phase = 'commit'
            if state.phase == 'commit':
                # Completed searches need not persist every scanned item. This
                # ordinary optimization is common to all backends, not novelty.
                state.positions, state.scored = [], []
                state.request_data.pop('vector', None)
                self.store.save(state, ledger)
                state.phase = 'done'
            if req.use_cache:
                self.cache.put(identity, state.selected)
            ledger.elapsed('total', start)
            guarantee = dict(scope='exhaustive_under_canonical_f64' if req.backend == 'full' else 'empirical_approximate',
                             semantic_quality='unreviewed', strict_certificate=False,
                             snapshot=self.snap.identity, ann_internal_read_bytes=None,
                             index_resident_bytes=int(sum(index.memory_usage for index in self.ann.values())),
                             result_cache_payload_bytes=self.cache.bytes)
            return Result(ResultKind.APPROXIMATE, self.snap.identity, contract, state.sources, guarantee,
                          ledger.dump(), cache_hit=state.cache_hit)
        except Exhausted as exc:
            # The caller can persist this state with a separately admitted commit.
            state.consumed = ledger.consumed.copy()
            ledger.elapsed('total', start)
            return Result(ResultKind.PENDING, self.snap.identity, contract, [],
                          dict(strict_certificate=False), ledger.dump(), state, str(exc))
        except ValueError as exc:
            ledger.elapsed('total',start)
            return Result(ResultKind.REJECTED,self.snap.identity,contract,[],
                          dict(strict_certificate=False),ledger.dump(),reason=str(exc))

    def close(self):
        if self.fts is not None:
            self.fts.close()
