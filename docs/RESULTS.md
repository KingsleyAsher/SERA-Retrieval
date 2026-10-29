# What the experiments currently establish

[English](RESULTS.md) | [简体中文](RESULTS.zh-CN.md)

I distinguish an implementation improvement from an architectural advantage. The current evidence supports the former and offers a limited mechanism signal; it does not yet establish stable superiority over strong retrieval baselines.

Stage 3.1 measured 4,800 requests. Cached seeds alone missed results, while candidate merging retained the full ANN search and added overhead. Neither path demonstrated a net advantage.

Stage 3.2 measured 10,560 requests across 44 configurations. Including ordinary warmup and candidate filling, it executed 14,304 searches. The workload uses 16 development families, 48 unique texts and 32 rewrites. Replays do not enlarge the independent sample population.

| Comparison | Observation | Interpretation |
|---|---|---|
| JSON merge C50 → compact merge C50 | 7.517 → 4.006 ms; match overhead about 96.9% lower; payload about 58.9% smaller | Repeatable layout improvement with identical replay results |
| Compact merge C50 versus ANN50 | 4.006 versus 4.168 ms pooled means | Round directions are inconsistent; filling makes the workflow more expensive |
| IVF16, total score budget 256 | Cold overlap 84.375%; warm C200 overlap 97.8125%; worst warm query 80% | Better average coverage at the same total score count, but worse latency and a remaining tail |
| IVF64, budget 512 | Cold already reaches 100% exact-vector top-10 overlap | Warm 512 versus cold 1213 is not evidence of additional warm-start savings |

The warm budget of 256 comprises 200 seed scores and 56 new scores. Those are not free extra candidates. Payload measurements exclude Python objects, transient copies and RSS. The overlap metric compares canonical vector top-10 sets; it is not semantic accuracy.

Semantic labels remain unreviewed. Uncached embedding-network latency, physical cold I/O, RSS, concurrent updates, complete crash recovery and large-scale behavior have not been validated. Stage-2 historical timings belong to the recorded pre-repair code, not a measurement of the repaired implementation. I make no production, novelty or generational-improvement claim from these results.
