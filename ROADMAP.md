# Research roadmap

[English](ROADMAP.md) | [简体中文](ROADMAP.zh-CN.md)

I am developing SERA to investigate a new retrieval architecture rather than optimize one isolated metric. The intended benefits are relevant results, faster responses, lower resource use, fresh results after updates, and predictable operation under load.

My working hypothesis is that candidate reuse, sparse activation, update repair and predictive work can share execution state, dependency tracking and one resource ledger. I will compare that design with mature systems equipped with the same ordinary caches, data layout and update capabilities.

| Stage | Research question | Current position |
|---|---|---|
| 1 | Can I freeze a credible quality/cost benchmark and resolve proposal errors? | Technical preparation complete; semantic labels still unreviewed |
| 2 | Can multiple backends share requests, snapshots, actions and budgets? | Reference implementation and correctness repairs delivered |
| 3.1 | Does cached-candidate reuse earn its lookup and fill cost? | Completed; no net advantage demonstrated |
| 3.2 | Do compact caches and seed-guided IVF improve the trade-off? | Completed; layout improvement and limited same-budget coverage gains |
| 3.3 | Can partial partitions resume correctly, and are geometric bounds useful? | Protocol prepared; implementation has not started |
| Remaining stage 3 | When are sparse routing, CPU calibration and prefetching worthwhile? | Pending |
| 4 | Can an independent path issue numerically valid exact certificates? | Theory under review; implementation pending |
| 5 | Does shared coordination add value beyond separate components? | Pending |
| 6 | Do benefits survive larger real corpora, updates and failures? | Pending |

I will finish and review each part before opening the next. Each protocol fixes its hypothesis, baseline, metrics, acceptance conditions and adjustment rules in advance. Negative results stay in the archive.

A 20% reduction in at least one declared major cost is a research challenge, not a forecast. I also require quality and freshness to hold, disclose regressions, and seek repeatable benefits on at least two meaningful workloads before an integrated review. A working prototype does not establish novelty or a generational improvement.

Scale-up will use real deduplicated text. Missing 10,000- or 50,000-chunk tiers will be reported rather than filled with duplicates. Expert-model training remains paused. Detailed stage records are available in the bilingual research index.
