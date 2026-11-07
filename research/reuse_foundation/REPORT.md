# Reuse foundation delivery · 2026-11-07

[English](REPORT.md) | [简体中文](REPORT.zh-CN.md)

I completed the first engineering slice: explicit read-only source adapters, isolated immutable snapshots, lifecycle/dependency guards, byte-bounded retention, cooperative work lanes and exact/ANN baselines. This work remains outside the frozen experiments. Stage 3.3, expert training and multi-view research have not been started by this delivery.

## Evidence and implementation

The [implementation guide](README.md) describes the APIs and formats. The module reuses the unchanged stage-two ledger, canonical inner product and USearch construction code. Knowledge-base patterns inform chunk/input identities, checksum checks, bounded retention and publish-after-sync. Memory patterns inform source-bound lifecycle, stale-response rejection and shared-work cancellation. The Python implementations are isolated adaptations; neither plugin is modified or installed. MIT notices and pinned upstream commits are in [provenance](provenance.json).

[Public checks](results/checks.json) pass **27 tests**, including invented native-format KB and memory inputs, UTF-16 ranges, FP32 provenance, invalid/duplicate inputs, lifecycle and scope transitions, unrelated-dependency preservation, ABA invalidation, budget admission/rollback, canonical ordering, committed resume, CLI process restart, async cancellation and publication failures. These tests do not establish extraction accuracy or live-host behavior. The [frozen regression record](results/frozen-regressions.json) passes all five public programs in a disposable archive copy, including the explicit review-fix predicates; original archive bytes remain unchanged.

## One synthetic measurement

Linux x86-64, Python 3.12.14, NumPy 2.5.4; USearch uses the repository-pinned dependency. Each arm runs in an independent process with the same seed **20261107**, **20,000** invented **1024-dimensional** unit vectors, k=10, a 64 MiB byte-cache allowance, one first query and three repetitions of the same query. Exact arms differ in batch size: all records versus windows of 256. ANN uses the frozen graph settings, 50 candidates and canonical reranking. Corpus import occurs before the first query; native ANN construction is included in its first-query time. “Cold” here means first application query, not a flushed OS page cache. Full data are in the [canonical benchmark](results/benchmark-20000.json).

| Arm | First query ms | Median repeated query ms | Process peak MiB | Exact-vector top-10 overlap |
|---|---:|---:|---:|---:|
| Full canonical scan | 1462.31 | 1500.40 | 537.19 | 100% |
| Windowed canonical scan | 1649.64 | 1484.89 | 379.02 | 100% |
| USearch + canonical rerank | 40907.92 | 925.33 | 720.55 | 30% |

Both exact arms return identical scores and stable IDs, and each charges **20,000** canonical scores and **163,840,000** logical vector bytes per query. Windowing lowers the observed process peak by about **29%** in this sample, but the repeated-query median changes by only about **1%**, and its first query is slower. This is evidence for a memory trade-off, not a reliable latency improvement. It does not satisfy or revise any existing research speed target.

ANN charges one index build and **81,920,000** FP32 index-input bytes on its first query. Canonical materialization and reranking account for **164,249,600** logical vector bytes initially and **409,600** on a warm query, in addition to unbounded native internal access observations. Its lower warm time accompanies only **30%** top-10 overlap on these random high-dimensional vectors. This is not a quality-matched win, an ANN tuning study or evidence about semantic embeddings. No parameters were retuned to improve the reported overlap.

The single withdrawal measurement is approximately 328 / 321 / 340 ms in the three arms. The store still serializes the whole immutable metadata snapshot on publication; selective dependency invalidation does **not** make that persistence path sublinear. Native matrices, snapshot objects, import work and the graph are outside the byte-cache allowance; peak RSS includes their lifetime contributions. Logical reads are not physical SSD traffic.

## Remaining boundaries and next review

Knowledge import requires a complete explicit source map. Memory import preserves records without inventing vectors. Native-format fixtures validate adapters, not a full installed-plugin integration. Permissions reflect the exported authority and replayed events, so live authorization changes must be delivered explicitly. Database relocation changes memory-source identity. Historical retention is not secure deletion.

The foundation has committed normal continuation, not crash-proof exactly-once execution. Ordinary sync/replace failures preserve an old manifest; there is no power-loss certificate or transaction spanning the source plugin and SERA. Scheduling is cooperative at callback checkpoints, and callback resource accounting must be supplied by its implementation. No semantic labels, real documents, paid calls, predictive work or expert training were used.

I stop this slice at engineering review. The next decisions remain whether to implement the already-written stage-3.3 protocol, reduce full-snapshot maintenance cost, and then design a separate update-workload comparison. Multi-view routing needs its own predeclared experiment. The new checks and random-vector measurement do not authorize advancing those parts or support a sparse-architecture net-benefit claim.
