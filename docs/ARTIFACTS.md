# Code and data inventory

[English](ARTIFACTS.md) | [简体中文](ARTIFACTS.zh-CN.md)

I keep one canonical executable and numeric record for each artifact. Both language editions below explain the full inventory; they do not create translated identifiers or diverging measurements. Paths and hashes are evidence identifiers, not natural-language prose.

Protocol files fix parameters; reports establish whether they were executed. A proposed rule in JSON is not a measured capability. Check summaries describe only their declared fixtures. Timings and counts must be associated with the matching stage and code hash. Semantic quality cannot be inferred from top-10 vector overlap.

| Artifact | Purpose and evidence boundary |
|---|---|
| [.gitignore](../.gitignore) | Python/local-environment exclusions plus private research and credential rules. |
| [BILINGUAL-MANIFEST.json](../BILINGUAL-MANIFEST.json) | Document pairing and the native-writing policy; not experimental evidence. |
| [CITATION.cff](../CITATION.cff) | Canonical machine-readable citation metadata; see the citation guide. |
| [docs/PUBLICATION-CHECKS.json](PUBLICATION-CHECKS.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [LICENSE](../LICENSE) | Unmodified authoritative Apache-2.0 terms; see the bilingual licensing guide. |
| [NOTICE](../NOTICE) | Canonical attribution notice with bilingual project explanation. |
| [PUBLICATION-MANIFEST.json](../PUBLICATION-MANIFEST.json) | Original publication source hashes, with editorial-version updates tracked explicitly. |
| [requirements.txt](../requirements.txt) | Pinned dependencies from the recorded experiment environment. |
| [research/ChatGPT/总体计划执行-v1/quality_metrics.py](../research/ChatGPT/总体计划执行-v1/quality_metrics.py) | Metric definitions that keep provisional judgments distinct from formal quality. |
| [research/ChatGPT/总体计划执行-v1/stage1-checks.json](../research/ChatGPT/总体计划执行-v1/stage1-checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/stage1-summary.json](../research/ChatGPT/总体计划执行-v1/stage1-summary.json) | Aggregate observations and paired diagnostic data; read stage-specific limitations. |
| [research/ChatGPT/总体计划执行-v1/stage1_protocol.json](../research/ChatGPT/总体计划执行-v1/stage1_protocol.json) | Frozen parameters and scoring/budget contract; companion report states whether executed. |
| [research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/check_review.py](../research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/check_review.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/checks.json](../research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/执行状态.json](../research/ChatGPT/总体计划执行-v1/执行状态.json) | Dated execution metadata; historical authorization strings are provenance, not new instructions. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/candidate_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/candidate_engine.py) | Stage-3.1 candidate-bank matching, rescore and merging reference. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/checks.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/finalize_report.py) | Aggregate saved experimental records; does not establish new runs. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/protocol.json) | Frozen parameters and scoring/budget contract; companion report states whether executed. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/results-summary.json) | Aggregate observations and paired diagnostic data; read stage-specific limitations. |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/run_ablation.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/run_ablation.py) | Historical candidate-reuse ablation; not a standalone public benchmark. |
| [research/ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/protocol.json) | Frozen parameters and scoring/budget contract; companion report states whether executed. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/execution_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/execution_engine.py) | Isolated stage-3.2 candidate executor and resumable IVF work. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/finalize_report.py) | Aggregate saved experimental records; does not establish new runs. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/layouts.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/layouts.py) | JSON/compact candidate storage and snapshot-bound IVF index. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/measure_startup.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/measure_startup.py) | Separate process/import timing probe with its recorded cache limitations. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/paired-diagnostics.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/paired-diagnostics.json) | Aggregate observations and paired diagnostic data; read stage-specific limitations. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/protocol.json) | Frozen parameters and scoring/budget contract; companion report states whether executed. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/results-summary.json) | Aggregate observations and paired diagnostic data; read stage-specific limitations. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/run_experiment.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/run_experiment.py) | Historical fixed-matrix replay; excluded private inputs are required. |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/startup-probe.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/startup-probe.json) | Separate startup observation; not a retroactive cold end-to-end replay. |
| [research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/check_math.py](../research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/check_math.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/math-checks.json](../research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/math-checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py](../research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py](../research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段二/checks.json](../research/ChatGPT/总体计划执行-v1/阶段二/checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/阶段二/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段二/finalize_report.py) | Aggregate saved experimental records; does not establish new runs. |
| [research/ChatGPT/总体计划执行-v1/阶段二/framework.py](../research/ChatGPT/总体计划执行-v1/阶段二/framework.py) | Shared request, snapshot, scoring, result and resource-ledger reference. |
| [research/ChatGPT/总体计划执行-v1/阶段二/inspect_inputs.py](../research/ChatGPT/总体计划执行-v1/阶段二/inspect_inputs.py) | Inspect the expected private input schema and structure. |
| [research/ChatGPT/总体计划执行-v1/阶段二/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段二/results-summary.json) | Aggregate observations and paired diagnostic data; read stage-specific limitations. |
| [research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py](../research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py) | Focused fictitious or arithmetic checks; read the script and recorded scope before running. |
| [research/ChatGPT/总体计划执行-v1/阶段二/run_stage2.py](../research/ChatGPT/总体计划执行-v1/阶段二/run_stage2.py) | Historical shared-backend comparison with private frozen assets. |
| [research/ChatGPT/总体计划执行-v1/阶段二/stage2_protocol.json](../research/ChatGPT/总体计划执行-v1/阶段二/stage2_protocol.json) | Frozen parameters and scoring/budget contract; companion report states whether executed. |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/after.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/after.json) | Before/after counterexample predicates, not performance measurements. |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/before.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/before.json) | Before/after counterexample predicates, not performance measurements. |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/boundary-checks.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/boundary-checks.json) | Recorded check outcome and declared verification scope; not a universal proof. |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/framework-before-ce251412.py](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/framework-before-ce251412.py) | Preserved pre-repair implementation; historical timing belongs to this version. |

Shared fields: `snapshot`/`revision` identify version scope; `score_contract` fixes ordering; `consumed` is cumulative resource work; `seconds` may be per invocation; `canonical_scores` and native ANN distance counts are different operations; `null` means unavailable, not zero. Read the owning protocol for exact field definitions.
