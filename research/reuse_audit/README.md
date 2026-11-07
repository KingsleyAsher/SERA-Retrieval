# State-reuse opportunity audit · 2026-11-07

[English](README.md) | [简体中文](README.zh-CN.md)

I audited the existing workload, reviewed a small evidence pool, and profiled where reuse could theoretically remove cost. This is an opportunity audit, not a new architecture comparison. No new mechanism is selected: real request locality and replayable update histories are absent, and semantic judgments remain provisional. The preceding geometric-bound negative result is unchanged.

## Workload and evidence card

The supplied frozen revision contains 1,213 chunks from 114 sources, using BGE-M3 dense1024. Ninety source metadata records contain an updated field; the field's real-world temporal meaning is not independently verified. The available questions are 16 authored triples, 48 distinct texts. Their order is not a natural session trace. The 1,216-row journal contains only `seq` and `id`: no timestamp, operation type or before/after body. Four stored aggregate states do not supply a request timeline or a reconstructible natural update history. The separate stage-one 120-family seed-qrels/audit assets were not supplied, and sealed splits were not opened.

I read the two highest canonical-vector evidence fragments for each anchor and judged the same fixed pair against all three wordings, producing **96 assistant-reviewed judgments across 48 questions**. Each private judgment binds query hash, chunk identity, version and content hash. It is explicitly provisional, not user-accepted gold; unjudged fragments remain unknown. No global nDCG@10, pooled recall, verified answerability or current-authority guarantee is reported.

| Provisional result within the fixed reviewed pair | Count |
|---|---:|
| Grade 0 / 1 / 2 judgments | 30 / 37 / 29 |
| Questions with at least one directly supporting fragment | 21 / 48 |
| Questions with both fragments judged irrelevant | 12 / 48 |
| Remaining questions: related but no direct support in this pair | 15 / 48 |

These are evidence-pool observations, not top-2 precision, top-10 quality or corpus answerability estimates. The pair was selected from each anchor rather than each rewrite's own ranking. The review found topic similarity without question support, navigation instead of methods, historical material mistaken for a current procedure, already-processed material that does not establish pending work, and incomplete coverage of compound questions. Relevance and current authority are separate: a topically direct old record still needs version/status review. Private review packets and rationales stay outside Git.

## Controlled cost observations

The fixed [protocol](protocol.json) was written before measurement. The unchanged stage-two full, ANN50/ef128 and hybrid executors share an isolated resident snapshot, source checks and SQLite FULL completion commits. Each backend receives one separately charged ordinary prewarm. Then 48 distinct query texts × 3 backends × 3 repetitions produce **432 observations**; method order rotates per query/repetition. Exact-request result caching is off in this profile. Initialization/import/prewarm costs remain in private records and the aggregate. Measurements use the current Linux/Python environment, not the user's Windows installation.

| Backend | Median total ms | Canonical-score removal ceiling | Materialized-source-check removal ceiling | Controlled ordinary-cache miss / hit ms |
|---|---:|---:|---:|---:|
| Full | 4.361 | 30.55% | 1.20% | 4.379 / 1.571 |
| ANN | 2.991 | 3.04% | 1.62% | 2.995 / 1.557 |
| Hybrid | 8.475 | 1.14% | 0.61% | 8.677 / 1.600 |

Removal ceilings are medians of each query's component/total ratio. They assume the entire component can disappear without replacement cost; neither scores for changed queries nor authorization/source checks can generally be removed that way. These are optimistic diagnostic ceilings, not observed savings. Source work here is hashing/checking materialized snapshot content, not original-file retrieval, parsing, cloud I/O or generation. Therefore the small source fraction cannot rule out source-I/O opportunities in a different live workload.

The hybrid lexical-search child span is about **61.64%** of total in this reference implementation, compared with **1.14%** for canonical reranking. Full canonical scoring is a substantial cost, but ANN already pays little for its 50 reranks. This motivates examining quality and ordinary lexical/index engineering before attributing gains to shared-state architecture. It does not establish semantic equivalence or choose a replacement mechanism. `prepare` contains ANN and lexical spans and is never added to them as if independent. Commit cost remains charged consistently.

An additional **144 controlled miss→identical-hit pairs** exercise the ordinary exact-request cache. All pairs preserve result IDs; hits still perform ten source reads/checks and one completion commit, with zero canonical rescoring. This is a deliberately constructed baseline control, not a measured natural hit rate or SERA contribution. The 48 authored questions are distinct by construction; that also cannot establish a real miss rate.

## Break-even and decision

The measured 16-anchor lookup median is about **0.0172 ms**, with precomputed anchor hashes and self-vector exclusion. A standalone lookup evaluates 16 scores and reads 131,072 logical query-vector bytes. Candidate payload lookup, fill and invalidation are not included, so it is an optimistic overhead reference, not the cost of a complete candidate-reuse mechanism.

The minimum requirement is `p * saved_cost > lookup + fill / uses + maintenance`. Actual valid-hit probability, amortization horizon and update-maintenance cost are unknown and stay null. Ignoring all costs except lookup gives source-only probability thresholds of roughly 32.7% / 35.2% / 33.6%, and scoring-only thresholds of roughly 1.3% / 19.3% / 18.6% for full/ANN/hybrid. Those numbers do not predict viability: useful quality-preserving reuse and the omitted costs have not been measured. Even ideal removal of source checks only accounts for around 0.6–1.6% of this measured pipeline.

I do not implement a new architecture mechanism on this evidence. The next inputs are a natural query sequence with scope/snapshot identity, and updates with operation type, affected identities and before/after versions or immutable payload references. Missing fields must stay missing. Semantic review should next expand to a shared full/ANN/hybrid result pool with independent/user adjudication, keeping current-authority and multi-facet coverage separate. No passive logging, plugin modification, model training or new embedding call was started.

## Reproduce and artifacts

```sh
python -m research.reuse_audit.measure --inputs-root /explicit/private-input-root --output /tmp/new-private-audit
# Review /tmp/new-private-audit/review-packet.json and save bound provisional labels privately.
python -m research.reuse_audit.analyze --private-run /tmp/new-private-audit --output /tmp/audit-summary.json
python -m unittest research.reuse_audit.test_audit -v
```

Canonical artifacts are `protocol.json`, `measure.py`, `analyze.py`, the invented `test_audit.py`, [results/summary.json](results/summary.json), [checks](results/checks.json) and [provenance](provenance.json). Seven new tests pass, covering hash/version/grade binding, incomplete-pool handling, no automatic gold promotion, impossible/unknown break-even cases, ordinary-cache source checks and aggregate privacy. The final measurement follows a preparatory run; anchor hashes were hoisted out of repeated lookup in the final run to avoid charging needless implementation work. The private evidence packet was byte-identical, so the same manual judgments remain bound. No parameter search or selection of a favorable performance run occurred.
