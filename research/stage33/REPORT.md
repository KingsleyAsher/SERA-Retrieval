# Stage 3.3 offline diagnostic completed · 2026-11-07

[English](REPORT.md) | [简体中文](REPORT.zh-CN.md)

I restored the original frozen inputs from an explicitly supplied archive into an external private directory. Database quick checks passed. The frozen database and source-metadata file matched the file hashes in the manifest, and the corpus coordinates matched its vector hash. Revision 1216, 1,213 chunks, 1024 dimensions and 16 families containing 48 distinct query texts were checked. The manifest's separate logical `metadata_sha256` was not independently reconstructed; it is not treated as the raw JSON-file hash.

The fixed **128 cases** now ran: 32 rewrites × KMeans16/64 × independent ANN50/200 support pools. These are **32 different queries**, not 128 independent samples. The ten frontier prerequisite groups, two geometry tests and new external-input-location test pass (**13 tests**); all **27** reuse-foundation tests also pass. The [public aggregate](results/offline-summary.json) and [source provenance](provenance.json) identify this delivery. Corpus text, query text/vectors, raw per-block diagnostics, partition coordinates and native indexes remain outside Git.

## Result: no observed pruning potential

| Layout / paid pool | Rewrites | Maximum additional scores avoidable by any tested bound | Rewrites with at least 20% avoidable | Median current-bound planning ms | Median support scoring ms |
|---|---:|---:|---:|---:|---:|
| IVF16 / C50 | 32 | 0 | 0 | 9.949 | 0.066 |
| IVF16 / C200 | 32 | 0 | 0 | 9.825 | 0.229 |
| IVF64 / C50 | 32 | 0 | 0 | 35.849 | 0.072 |
| IVF64 / C200 | 32 | 0 | 0 | 35.557 | 0.294 |

The sphere-derived IP bound, radial-statistical bound, direct IP ball bound, their combination and old-query transfer all eliminate **zero unscored eligible vectors** using the legitimately paid current support threshold. Even the diagnostic true top-10 oracle threshold leaves the combination unable to exclude a block. The smallest combined-bound-minus-paid-threshold margin is still about **0.1503**. This is substantive looseness in the observed geometry, rather than a near-tie hidden with a numerical tolerance.

Across **5,120 block comparisons**, there were **zero observed raw coverage violations**. No epsilon correction was applied. This finite check does not prove floating-point conservatism, a probability guarantee or strict certification. It also does not establish semantic quality: the development labels remain unreviewed.

## Cost and attribution

Each C50/C200 case pays 50/200 canonical support scores and **409,600 / 1,638,400** logical vector bytes. Anchor matching costs 16 scores and 131,072 bytes per standalone arm. The driver physically shares each query/layout match between the two C cases; adding all per-case matching counts would overstate this shared replay's physical work.

ANN pool fill is separate: each C uses one native index build and 16 anchor searches; input is 4,968,448 FP32 bytes per build. Measured build/fill time is about 0.251 / 0.258 seconds for C50/C200. The two partition/statistics builds take about 0.384 / 0.325 seconds and have JSON statistics payloads of **367,788 / 1,454,430 bytes**. Assignment, centers, postings and statistics have private persisted fingerprints.

Full-score oracle evaluation costs 1,213 scores and 9,936,896 logical vector bytes per case. L2 reference enumeration has an additional 1,213-vector pass. Old support scores and old-bound construction remain in the evaluation ledger. Current-bound planning is now timed separately from support scoring and oracle/L2/old-bound reference work. The reference implementation's planning measurements include Python serialization used for payload accounting; they are not the intrinsic cost of an optimized native geometric kernel. Evaluation medians range from approximately 13.5 to 41.7 ms. These timings are diagnostics, not retrieval latency claims. Update maintenance was not measured.

## Decision and reproducibility

Gate two is complete as a diagnostic with a negative result. The draft 8/32–20% screening rule was not promoted to a new acceptance criterion; every fixed configuration is at 0/32 regardless. I therefore retain the failure and stop this bound configuration. I do not expand its parameter grid on the same development queries, start online stopping or train a model. This result limits this geometric-bound path on this snapshot; it does not invalidate every state-reuse or sparse-retrieval architecture.

```sh
python -m research.stage33 --output /tmp/stage33-checks.json
python -m research.stage33.private_replay --inputs-root /explicit/private-input-root --output /tmp/new-private-stage33-run
python -m research.stage33.summarize --input /tmp/new-private-stage33-run/diagnostics.json --output /tmp/offline-summary.json
```

The external input root contains `.private-kb-experiments/` and `ChatGPT/` in the supplied layout. No repository symlink or private upload to Git is needed. The initial full replay was retained privately; a second replay after separating measurement/accounting roles supplies the canonical published aggregate. It was a correctness/accounting revision, not parameter selection. No embedding or network inference call was made. A review of this report is the next stopping point before any further research part.
