# Stage 3.3 implementation and partial delivery · 2026-11-07

[English](README.md) | [简体中文](README.zh-CN.md)

I implemented the first gate of the [existing protocol](../ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/下一部分协议.en.md) in an isolated executor. Ten prerequisite groups and two geometry tests pass. **The second gate remains blocked:** the private frozen inputs are absent, so the specified 128 diagnostic cases have not run. This delivery establishes neither geometric pruning potential nor an architecture performance advantage. Expert training, online bound stopping and strict certification remain disabled.

## Execution and accounting

`frontier.py` imports the unchanged canonical float64 score and parent Ledger through the reuse foundation bridge. `FrontierEngine(store, snapshot, lists, centers)` checks an exact one-to-one partition of the snapshot and fingerprints the snapshot, immutable centers and postings. It uses the existing Request/Scope contract. `run(request, seeds=(), scan_budget=None, state=None)` returns a dictionary with kind, items, coverage, cumulative resources, continuation and checkpoint persistence. `restore(signature)` reads committed state from an isolated SQLite store's `stage33_states` table. The original stage-3.2 implementation and results are not overwritten.

An opened partition is retained as `active_partition` even after removal from `order_frontier`. Enumeration advances `enumeration_cursor`; accepted positions remain in `pending_positions` until `score_cursor` covers their scores. Already-scored seeds are deduplicated by snapshot position. A partition becomes completed only when its eligible members are covered. `coverage()` explicitly reconstructs all unscored eligible members, including active tails and pending work. This conservative enumeration is intended for correctness; it is not a fast bound heap or an online pruning implementation.

Seeds are explicit ID/version pairs from the same snapshot. This executor consumes a paid pool rather than performing anchor selection or ANN filling itself. Metadata verification and payload bytes are recorded. Each new score atomically admits `canonical_scores`, its seed/new-scan classification, and `dimension*8` vector bytes. Normal resume retains both consumed resources and cursors. Extra checkpoint commits are charged per invocation. Unknown hard counters are rejected; a fixed scan target completes an approximate response, while an exhausted hard budget returns pending. Empty scopes and eligible sets smaller than K finish normally. Complete scanning preserves canonical ID tie-breaking, materialized-source checks and committed completion state. There is no full-result cache bypass in this executor.

Public checks reproduce the 0.5 seed / 0.6 first member / 0.95 tail case across a database close and new executor. They also cover interrupted enumeration, the final pending score, zero/one seed budgets, atomic byte admission, duplicated seeds, popped active coverage, N<K, empty scope, fixed-target versus pending termination, changed scope/snapshot, tampered checkpoints and source-fetch continuation. Physical exactly-once execution across crashes and power loss is not claimed.

## Offline diagnostics

`diagnostics.py` implements block centers, radii, 16 contiguous-subspace radial intervals, maximum member norms and squared norms. It reports sphere/statistical/max-combined L2 lower bounds, direct IP ball upper bounds, the general norm-aware L2-to-IP bridge, and old-query transfer using beta times query displacement. Each case separates a current threshold obtained by rescoring the paid pool from the full-score oracle threshold. Already-paid unique positions are subtracted from possible avoided scores. Whole-block and unscored counts are separate, and sphere-only/stat-only/both/neither counts retain all blocks as the denominator.

Coverage violations are retained with raw signed gaps, without an epsilon repair. Ordinary float64 values never become machine certificates. Oracle scores, old support scores and old-bound construction remain in explicit evaluation ledgers; transfer is an offline diagnostic, not an assumed free online capability. Statistical construction bytes, storage payload, matching, ANN fill and support scores have separate cost records. Maintenance costs and numeric error certification remain unmeasured. The two invented geometry tests check formulas and cost separation, not the production dataset's screening signal.

`private_replay.py` provides the fixed 32 rewrites × 2 layouts × 2 pool sizes loop. It uses the historical loader without launching its benchmark, rebuilds KMeans16/64 with protocol settings, saves partition/statistic fingerprints, fills independent ANN50/200 anchor pools and selects anchors by actual query-vector score with stable ID ties and self-vector exclusion. Family labels do not choose the anchor. The first driver entry check exits with code 2 when any frozen asset is absent; **the full private driver has not been exercised end to end here**. Its output must be a new private directory outside the repository. It contains no network or embedding fallback. The proposed 8/32 and 20% screening rule remains a draft; this delivery makes no screening decision.

## Reproduce and current stop

```sh
python -m research.stage33 --output /tmp/stage33-checks.json
python -m research.stage33.private_replay --output /tmp/new-private-stage33-run
```

The [check record](results/checks.json) pins source hashes and reports **12 tests passed**. The replay preflight was executed and correctly blocked. Missing inputs, at the historical loader's expected paths, are:

- `research/.private-kb-experiments/plan-v1-stage1/frozen.sqlite`
- `research/.private-kb-experiments/plan-v1-stage1/source-metadata.json`
- `research/.private-kb-experiments/plan-v1-stage1/manifest.json`
- `research/.private-kb-experiments/embedding-cache.sqlite`
- `research/ChatGPT/真实查询复用研究-v0.14/queries.json`

These must describe the original 1,213 chunks, revision 1216, BGE-M3 dense1024 and cached 48 query vectors. Synthetic inputs are not substituted. No raw private diagnostic output belongs in the public repository.

I stop with gate one verified and gate two input-blocked. The immutable protocol, stage-3.2 artifacts and earlier engineering results are preserved. Restoring the specified frozen assets enables the offline replay and a new report; it does not authorize online stopping. A successful second gate still needs evidence review before that next part.
