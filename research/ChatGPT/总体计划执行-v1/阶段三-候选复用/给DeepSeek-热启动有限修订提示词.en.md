# Research brief: a limited warm-start revision

[English](给DeepSeek-热启动有限修订提示词.en.md) | [简体中文](给DeepSeek-热启动有限修订提示词.md)

I want a small executable specification, not another expanded system architecture. The current candidate-merging experiment does not modify USearch search state. Retain that distinction and investigate a controllable IVF reference for actual frontier changes.

Work from the fixed BGE-M3 1,213-chunk snapshot and existing development queries. Stage-3.1 ANN50 reaches 100% vector overlap at about 4.179 ms; seed C200 has 96.25% mean and 70% minimum, while merged C200 costs about 8.361 ms without reducing native distance work. These are controlled development observations, not semantic accuracy or a universal rejection of reuse.

Specify how legal current-query seed scores affect initialization, list priority, visited/scored sets, pending work and stopping. The total score/read allowance includes seeds. Persist every cursor needed to resume a partial list. Do not mark a list completed merely when opened. Keep ordering heuristics distinct from valid upper bounds covering all unfinished regions.

For query-difference migration, state the vector norm assumptions, support IDs/versions, threshold direction and scope coverage. K legal supports may suffice without old global exact top-K; using a scalar old threshold alone is inadequate. No fixed .99-similarity window, free current-query oracle or automatic probability guarantee is allowed.

Propose matched cold/warm comparisons with common layout, scope, source handling and budget. Separate seed initialization, ordering and stopping effects. Preserve ANN and cold IVF strong points. Deliver minimal state transitions, mathematical premises, counterexamples and a finite experiment proposal. Do not run private experiments, access training, add a model or change the research acceptance criteria as part of this brief.
