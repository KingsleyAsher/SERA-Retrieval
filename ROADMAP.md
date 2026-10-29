# Research roadmap / 总体路线

Five objectives: semantic quality, latency, resource efficiency, update freshness, stability.
Core hypothesis: shared execution state, dependency invalidation and a common resource ledger can avoid repeated work beyond isolated components.

| Stage | Scope | Status |
|---|---|---|
| 1 | Frozen corpus, proposal corrections, 120 query families and relevance review | Technical preparation done; labels unreviewed |
| 2 | Shared executor, snapshots, budget ledger, full / ANN / hybrid baselines | Delivered with correctness repairs |
| 3.1 | Cache-only and candidate-merge ablations | Done; no strong-baseline net benefit |
| 3.2 | Compact layout and controllable seed-guided IVF | Done; layout improvement and local coverage signal |
| 3.3 | Partial-partition continuation, atomic seed accounting, offline bound diagnosis | Protocol only; not started |
| Remaining 3 | Sparse execution, independent CPU calibration, budgeted prefetch | Pending |
| 4 | Independent strict certification branch | Theory preparation; implementation pending |
| 5 | Joint framework versus equally equipped strong baselines | Pending |
| 6 | Real deduplicated scale-up, recovery, concurrent updates, shadow use | Pending |

A 20% reduction in one declared major cost is a research challenge, not a promise. All other dimensions and regressions must be reported. Repeatable benefit on at least two meaningful workloads is required before integrated-prototype acceptance. Semantic conclusions require reviewed labels. Do not manufacture scale using repeated copies of data.

每一部分固定假设、基线、指标、通过／调整条件，完成后报告并等待负责人确认。失败记录保留，不通过更换指标或选择弱基线制造结论。详细中文执行口径见 [研究总纲](research/ChatGPT/总体计划执行-v1/执行总纲.md)。
