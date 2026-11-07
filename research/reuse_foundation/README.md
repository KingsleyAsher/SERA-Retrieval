# Reusable retrieval foundations

[English](README.md) | [简体中文](README.zh-CN.md)

I use this isolated module to bring source validation, lifecycle handling and resource management from my knowledge-base and memory projects into SERA. It is an engineering deliverable alongside the frozen research archive. It does not advance stage 3.3, train experts, change the BGE-M3 experiment, or establish a sparse-routing advantage. Results and limits are in the [report](REPORT.md).

## Interfaces and isolation

Run the module from the repository root with the existing pinned `requirements.txt`. Python 3.12 was used for this delivery. No new runtime dependency is introduced. The module imports the unchanged stage-two `Ledger`, canonical score function and USearch construction code; new stores contain only `reuse_*` tables. Opening a foreign database as a destination is rejected before changing its journal mode.

| Interface | Contract |
|---|---|
| `export_source(kind, path)` | Read explicitly named knowledge or memory assets; return `{format:1, records, source_manifest}`. Never scan for a private library. |
| `import_snapshot(records, store, ledger=None)` | Validate all records, normalize explicitly declared FP32 input, atomically create a separate snapshot, and return import/resource metadata. |
| `FoundationStore.apply_events(events, ledger=None)` | Atomically apply explicit events with immutable event IDs; conflicting retries fail. |
| `capture_dependencies` / `validate_dependencies` | Bind data, access scope, lifecycle, representation and store ownership; optionally bind the whole dataset epoch. |
| `Baselines.run` | Execute exact or ANN retrieval with shared scoped input and canonical reranking; return coverage, cumulative resources and a committed continuation when pending. |
| `Resources.run_shared` | Coalesce byte computations with identical keys and dependencies. Work callbacks account for their own I/O/computation against the supplied parent ledger. |
| `run_checks()` / `run_benchmark()` | Exercise synthetic correctness or independent-process measurements. |

Records require `namespace`, `id`, `version`, `text`, `content_sha`, `path`, `scope`, `visible`, `status`, `policy_revision`, `preprocessing`, plus optional `model`, `dimension`, `dtype`, `vector` and `provenance`. Hashes use SHA-256 of UTF-8 text. Status is `active`, `pending`, `withdrawn`, `superseded` or `deleted`. Vector payloads require model, dimension and explicit `float32` or `float64` dtype. Invalid records fail the batch; absent vectors remain absent and appear in retrieval coverage.

Each import is a **complete snapshot of every namespace it contains**. Omitted prior members become tombstones. An empty source export must name its namespace in `source_manifest`. Replaying an identical export returns its original import receipt without changing current state; this prevents retries from reviving an intervening deletion. To restore an earlier state intentionally, issue a new explicit event or a new authoritative source revision. Different source identities retain separate provenance even when immutable vector bytes deduplicate.

FP32 conversion preserves the original little-endian byte hash, promotes coordinates, and normalizes in float64. It receives its own conversion identity. Float64 input must already satisfy the frozen normalization contract. New converted snapshots are never substituted into historical experiments. Inputs with different model, preprocessing, dimension or conversion contracts cannot participate in one vector query. Queries supply a canonical normalized float64 vector and explicit scopes; CLI access defaults to `global`.

## Source formats

**Knowledge bundle.** An explicit directory contains the plugin's native `manifest.json`, `catalog.json` and referenced `vectors-N.bin` shards. A required `source-map.json` supplies facts the native catalog does not contain:

```json
{
  "format": 1,
  "namespace": "explicit-library-identity",
  "policy_revision": "explicit-policy-version",
  "model": "BAAI/bge-m3",
  "preprocessing": "explicit-model-input-and-chunk-contract",
  "documents": {
    "notes/example.md": {
      "text": "explicitly exported complete source text",
      "revision": "the catalog revision",
      "content_sha": "SHA-256 of text",
      "visible": true,
      "status": "active",
      "scope": "global"
    }
  }
}
```

The adapter checks source hashes and revisions, interprets chunk offsets as JavaScript UTF-16 code units, reconstructs the embedding input hash, and verifies every present vector's slot, length and checksum. Missing vector mappings represent pending embeddings. Missing checksums on present vectors fail closed; this first adapter does not repair legacy unchecked shards. File identity/size/mtime/ctime changes during export reject the bundle. The source map is a caller-supplied export, not independent proof of real-world truth or live permission authority. It must be regenerated when that authority changes.

**Memory database.** The adapter opens an explicitly named SQLite database with `mode=ro` and reads a SQLite snapshot, including WAL-visible data. It reads the plugin's `plugin_memory_entries`, source controls, and available claim/pending-change tables. Global and project scopes remain distinct. Excluded/deleted sources are inaccessible; withdrawal, supersession and pending changes are represented explicitly. No extraction model or embedding service runs. These plugin records normally have no vectors, so importing them does not make semantic search available. Source identity is derived from the resolved database path; relocated copies intentionally have a different namespace. SQLite can manage WAL shared-memory sidecars; no source data or schema is written by the adapter.

The public `fixtures.py` builds invented native-format examples for both adapters. Live plugin installation and private-store export are outside this delivery.

## Lifecycle and execution

Events contain `event_id`, `namespace`, `id` and `action`. `change`/`correct` carry a complete replacement `record` with the same identity and a new source version. `permissions` supplies a new `policy_revision`, `visible`, and optionally `scope`. Other actions are `withdraw`, `delete`, `pending` and `activate`. Ordinary failures roll back the whole event batch; issued ledger charges are not refunded.

Immutable historical snapshots remain distinct from current authorization. Current retrieval selects active records; historical retrieval can expose an older state only when the source remains accessible under current permissions. Output includes both snapshot `status` and `current_status`. Deletion prevents historical access through this API but is not secure erasure of archived SQLite pages or prior exports.

Per-record dependency stamps allow unrelated derived work to survive updates. Full retrieval binds the dataset epoch as well, because an added or changed competitor can alter top-k even when previously selected records are unchanged. Every mutation advances the epoch transactionally. Serial dependencies prevent an active→withdrawn→active cycle from reviving old tasks. Async results are checked before retention and return; cancelling the last waiter blocks publication even if the callback suppresses cancellation. One remaining live waiter may finish shared work after another waiter cancels.

Retention is capped by key-plus-payload bytes, not Python heap size. Over-budget values still participate in the current computation. Background work is serialized and yields at explicit batch checkpoints while foreground work is active. Callbacks must actually use these checkpoints; native synchronous ANN calls cannot be interrupted internally. There is no autonomous scheduler or prefetch predictor.

Exact scanning retains bounded top-k with deterministic stable numeric IDs and the existing float64 inner product. ANN uses frozen USearch construction and the same canonical reranking. At most one native engine is retained per baseline object; its matrix and native allocations are **outside** the byte-cache budget. Actual process memory is measured separately. All new canonical scores and logical vector accesses are charged before their batch. A returned pending checkpoint preserves scoring/source cursors and scores; normal resume does not repeat completed scoring. Its payload must match committed state, including ownership and request signature. If the commit budget itself is unavailable, the response explicitly says the checkpoint was not persisted.

Unknown hard limits, especially native distance/visit counters, are rejected. Logical vector bytes include access served by cache; cache read bytes and native ANN work are observations. Materialized metadata preparation, SQLite page traffic and arbitrary callback CPU time are not physical I/O or CPU hard caps. Power-loss recovery, physical exactly-once execution and atomic transactions spanning plugin and SERA stores are not claimed.

## Commands and artifact inventory

```sh
python -m research.reuse_foundation checks --output /tmp/reuse-checks.json
python -m research.reuse_foundation benchmark --output /tmp/reuse-benchmark.json
python -m research.reuse_foundation.verification --output /tmp/frozen-regressions.json
python -m research.reuse_foundation export --kind knowledge --source /explicit/bundle --output /tmp/export.json
python -m research.reuse_foundation export --kind memory --source /explicit/memory.sqlite --output /tmp/memory-export.json
python -m research.reuse_foundation import --input /tmp/export.json --store /tmp/reuse.sqlite
python -m research.reuse_foundation events --input /tmp/events.json --store /tmp/reuse.sqlite
python -m research.reuse_foundation query --store /tmp/reuse.sqlite --vector /tmp/query.json --output /tmp/result.json
```

For budget interruption, add `--limits '{"canonical_scores":7}'`, then rerun the identical query with `--resume <committed-signature>` and an adequate cumulative limit. Scope, snapshot, backend, k and window remain bound to the signature. CLI outputs contain only a receipt; source text and retrieved evidence are written only to the requested output. Keep real exports and stores outside version control.

Canonical code: `common.py` (frozen bridge), `sources.py` (adapters), `store.py` (snapshots/events), `runtime.py` (dependencies/cache/lanes/publication), `baselines.py`, `fixtures.py`, `test_foundation.py`, `benchmark.py`, `verification.py`, package initialization and CLI. `results/` holds synthetic checks, benchmark and frozen regression evidence. `provenance.json` pins code/result hashes and upstream source identities. The two `licenses/*-MIT.txt` files preserve upstream license texts. This Python implementation borrows design patterns, not plugin runtime integration; attribution remains separate from validation.
