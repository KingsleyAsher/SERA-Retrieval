# Results and limitations / 结果边界

Source: [stage 3.2 report](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/阶段三第二部分报告.md), with frozen summaries beside it.

- Stage 3.1: 4,800 measured requests; seed-only misses and merge overhead did not show net benefit.
- Stage 3.2: 44 configurations, 10,560 measured requests, 14,304 total searches including warmup/fill; 10 mechanics checks.
- Compact merge C50: 7.517 → 4.006 ms versus JSON, same replay outputs. Match overhead ~96.9% lower; payload ~58.9% lower. Payload excludes Python objects and transient/RSS overhead.
- Against ANN50 (4.168 ms), the pooled compact-merge difference is not repeatable across rounds; candidate-fill lifecycle cost remains higher.
- IVF16 / total 256 scores: cold mean top-10 overlap 84.375%, warm C200 97.8125%; worst warm 80%, latency worse. Seed 200 + new 56 = 256, not free extra work.
- IVF64 cold / 512 already reaches 100% vector overlap; comparing warm / 512 against cold / 1213 does not establish warm-start savings.

Only 32 rewrites from 16 development families were used for these comparisons. Labels are unreviewed. Embedding network latency, physical cold I/O, RSS, concurrency, full crash recovery and large-scale behavior are not validated here. Earlier stage-2 timing is tied to the recorded pre-repair code hash and is not a remeasurement of repaired code.

These are controlled observations, not production guarantees, novelty validation, or a generational improvement claim.
