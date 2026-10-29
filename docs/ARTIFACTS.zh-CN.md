# 代码与数据资料清单

[English](ARTIFACTS.md) | [简体中文](ARTIFACTS.zh-CN.md)

我为每项代码和数值记录保留单一规范版本。下面的两种语言说明覆盖完整资料清单，不改写标识，也不制造测量值不同的副本。路径与哈希用于定位证据，不作为自然语言正文互译。

协议文件固定参数，是否运行由阶段报告确定；JSON 中的拟议规则不等于已测能力。检查汇总只说明其声明的夹具范围，耗时和计数必须与阶段及代码哈希对应。向量前十重合不能推出语义质量提升。

| 资料 | 用途与解释边界 |
|---|---|
| [.gitignore](../.gitignore) | Python／本地环境及私人研究资产、凭据的排除规则。 |
| [BILINGUAL-MANIFEST.json](../BILINGUAL-MANIFEST.json) | 文档配对与直接写作约定，不属于实验结果。 |
| [CITATION.cff](../CITATION.cff) | 规范机器可读引用元数据，解释见引用说明。 |
| [docs/PUBLICATION-CHECKS.json](PUBLICATION-CHECKS.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [LICENSE](../LICENSE) | 保持原文的 Apache-2.0 正式条款，配套双语许可说明。 |
| [NOTICE](../NOTICE) | 规范归属文件，另有中英文项目说明。 |
| [PUBLICATION-MANIFEST.json](../PUBLICATION-MANIFEST.json) | 原始发布来源哈希，文字版本变化另行留痕。 |
| [requirements.txt](../requirements.txt) | 记录实验环境中的固定依赖版本。 |
| [research/ChatGPT/总体计划执行-v1/quality_metrics.py](../research/ChatGPT/总体计划执行-v1/quality_metrics.py) | 区分暂定判断与正式质量结论的指标定义。 |
| [research/ChatGPT/总体计划执行-v1/stage1-checks.json](../research/ChatGPT/总体计划执行-v1/stage1-checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/stage1-summary.json](../research/ChatGPT/总体计划执行-v1/stage1-summary.json) | 汇总观察与配对诊断数据，须结合阶段限制解释。 |
| [research/ChatGPT/总体计划执行-v1/stage1_protocol.json](../research/ChatGPT/总体计划执行-v1/stage1_protocol.json) | 冻结参数及评分／预算契约，是否执行以对应报告为准。 |
| [research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/check_review.py](../research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/check_review.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/checks.json](../research/ChatGPT/总体计划执行-v1/修订验收与主会话交接-2026-10-29/checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/执行状态.json](../research/ChatGPT/总体计划执行-v1/执行状态.json) | 带日期的执行状态；历史授权字段用于来源追踪，不构成新指令。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/candidate_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/candidate_engine.py) | 阶段三第一部分候选匹配、重评分和合并参考。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/checks.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/finalize_report.py) | 汇总既有记录，不能视为产生新实验。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/protocol.json) | 冻结参数及评分／预算契约，是否执行以对应报告为准。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/results-summary.json) | 汇总观察与配对诊断数据，须结合阶段限制解释。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-候选复用/run_ablation.py](../research/ChatGPT/总体计划执行-v1/阶段三-候选复用/run_ablation.py) | 历史候选复用消融，不是可直接运行的公开基准。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/protocol.json) | 冻结参数及评分／预算契约，是否执行以对应报告为准。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/execution_engine.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/execution_engine.py) | 阶段三第二部分隔离执行器及可接续 IVF。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/finalize_report.py) | 汇总既有记录，不能视为产生新实验。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/layouts.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/layouts.py) | JSON／紧凑候选表示与快照绑定 IVF 索引。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/measure_startup.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/measure_startup.py) | 独立进程／导入耗时探针，缓存限制按原记录说明。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/paired-diagnostics.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/paired-diagnostics.json) | 汇总观察与配对诊断数据，须结合阶段限制解释。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/protocol.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/protocol.json) | 冻结参数及评分／预算契约，是否执行以对应报告为准。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/results-summary.json) | 汇总观察与配对诊断数据，须结合阶段限制解释。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/run_experiment.py](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/run_experiment.py) | 历史固定矩阵回放，依赖未公开私有输入。 |
| [research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/startup-probe.json](../research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/startup-probe.json) | 独立启动观察，不回填成原回放的冷启动端到端耗时。 |
| [research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/check_math.py](../research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/check_math.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/math-checks.json](../research/ChatGPT/总体计划执行-v1/阶段三后方案审阅-2026-10-29/math-checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py](../research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py](../research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/checks.json](../research/ChatGPT/总体计划执行-v1/阶段二/checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/finalize_report.py](../research/ChatGPT/总体计划执行-v1/阶段二/finalize_report.py) | 汇总既有记录，不能视为产生新实验。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/framework.py](../research/ChatGPT/总体计划执行-v1/阶段二/framework.py) | 共享请求、快照、评分、结果及资源账本参考实现。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/inspect_inputs.py](../research/ChatGPT/总体计划执行-v1/阶段二/inspect_inputs.py) | 检查预期私有输入的模式与结构。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/results-summary.json](../research/ChatGPT/总体计划执行-v1/阶段二/results-summary.json) | 汇总观察与配对诊断数据，须结合阶段限制解释。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py](../research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py) | 定点虚构或算术检查，执行前核对脚本和已声明验证范围。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/run_stage2.py](../research/ChatGPT/总体计划执行-v1/阶段二/run_stage2.py) | 依赖私有冻结资产的历史多后端比较。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/stage2_protocol.json](../research/ChatGPT/总体计划执行-v1/阶段二/stage2_protocol.json) | 冻结参数及评分／预算契约，是否执行以对应报告为准。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/after.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/after.json) | 反例修复前后判据，不是性能测量。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/before.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/before.json) | 反例修复前后判据，不是性能测量。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/boundary-checks.json](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/boundary-checks.json) | 已记录检查结果及验证范围，不是通用正确性证明。 |
| [research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/framework-before-ce251412.py](../research/ChatGPT/总体计划执行-v1/阶段二/独立审阅修复/framework-before-ce251412.py) | 保留的修前实现，相关历史耗时属于此版本。 |

共同字段说明：`snapshot`／`revision` 标识版本范围；`score_contract` 固定排序；`consumed` 为累计资源工作；`seconds` 可能只对应本次调用；`canonical_scores` 与原生 ANN 距离次数不是同一种操作；`null` 表示不可用，不是零。精确定义以所属协议为准。
