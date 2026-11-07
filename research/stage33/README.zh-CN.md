# 阶段三第三部分：实现与交付 · 2026-11-07

[English](README.md) | [简体中文](README.zh-CN.md)

完整[离线诊断报告](REPORT.zh-CN.md)已替代早先的输入阻塞检查点。固定 128 情形全部运行，未观察到剪枝潜力。

我已依据[既有协议](../ChatGPT/总体计划执行-v1/阶段三-前沿接续与界诊断协议/下一部分协议.md)实现独立执行器，完成第一道门：10 组前置检查和 2 项几何检查全部通过。第二道门在初次交付时受输入缺失阻塞，现已使用所提供的原始冻结输入运行完毕，结果为负。本次不能判断界是否具有足够剪枝潜力，也不能证明架构有性能优势。在线界停止、专家训练和严格认证均未启用。

## 接续状态和计费

`frontier.py` 通过复用基础桥接未修改的规范 float64 评分与父 Ledger。`FrontierEngine(store, snapshot, lists, centers)` 检查分区对快照成员的一一覆盖，固定不可变中心与 posting，并保存依赖指纹。请求继续采用既有 Request／Scope；`run(request, seeds=(), scan_budget=None, state=None)` 返回状态、结果、未完成覆盖、累计资源及接续信息。`restore(signature)` 从隔离数据库的 `stage33_states` 读取已提交状态，不覆盖阶段三第二部分代码与结果。

分区从访问队列取出后仍保留为 `active_partition`。`enumeration_cursor` 记录枚举位置，合法项先进入 `pending_positions`，实际评分完成后才推进 `score_cursor`。当前查询已经计分的种子按位置去重，不能再读向量或重复评分。只有合法成员全部覆盖后才能标记 completed。`coverage()` 保守重建所有尚未评分的合法成员，包含未开始分区、活动尾部和 pending 项。这是正确性实现，不是快速界堆或在线剪枝。

输入种子为同快照的 ID／版本对。执行器使用明确提供的已付候选池，本身不做旧查询匹配或 ANN 填充；这些成本在离线驱动中另记。种子元数据验证与载荷读取记录在账本中；每次新评分发起前，同时准入规范评分次数、种子／新增分类和 `维度×8` 向量字节。正常恢复沿用原累计消耗和游标，额外 checkpoint 提交单列。不支持的硬计数被拒绝；固定扫描目标结束返回近似结果，硬资源不足返回 Pending。空范围、N<K 可以正常穷尽。完整扫描保留规范 ID 同分顺序、快照正文核验及完成提交，没有整次结果缓存绕行。

公开检查保留 0.5 种子、0.6 首成员、0.95 尾部的反例，关闭数据库并重建执行器后仍能找到 0.95。其他检查覆盖 posting／评分分别中断、最后 pending 项、种子预算为零／一、字节原子准入、种子重复、活动分区出队、N<K／空集、固定结束与 Pending、范围／快照变化、接续载荷篡改及取证接续。没有声明崩溃后的物理恰好一次或断电保证。

## 离线界诊断实现

`diagnostics.py` 构建块中心、半径、16 个连续子空间径向区间、最大成员范数与范数平方，输出球界、统计界、max 组合 L2 下界、直接 IP 球上界、带实际范数项的 L2→IP 上界及带 βΔ 的旧查询界迁移。阈值来自当前查询对已付候选池的重评分；全量 top-K oracle 单独列出并计入评估账。潜在省评分数扣除已付种子，整块可排除数量与未评分唯一项分别报告，sphere_only／stat_only／both／neither 的分母保留全部块。

数值覆盖违反保留原始差值，不加任意 epsilon 修补。普通 float64 观测值不是机器证书。oracle、旧支持评分和旧界构造显式计入评估账；迁移仅作离线比较，不能被解释为免费在线能力。统计构建、存储载荷、匹配、ANN 填充和支持评分分别保留成本；维护成本与数值认证尚未测量。两项虚构几何检查只核对公式与账本角色，不替代真实开发集的筛选信号。

`private_replay.py` 提供 32 个改写×2 个布局×2 个候选池的固定循环，调用历史只读输入加载器而不启动旧基准，按协议参数重建 KMeans16／64 并保存分区及统计指纹。ANN50／200 独立填充旧锚点候选池，依据当前查询真实向量分数、稳定 ID 同分规则和自身向量排除来选择锚点，不使用家族标签匹配。缺少任一冻结资产时，入口以退出码 2 停止。**完整私有驱动现已用上传的原始数据端到端运行**。输出必须是仓库外的新私有目录，没有联网或补嵌入回退。8/32 与 20% 继续作为原协议待确认的筛选草案，本轮不作通过判定。

## 命令、缺口与停止点

```sh
python -m research.stage33 --output /tmp/stage33-checks.json
python -m research.stage33.private_replay --output /tmp/new-private-stage33-run
```

[检查记录](results/checks.json)固定新增源码哈希并记录 **13 项测试通过**，包括新增外部输入目录检查。原入口曾因输入缺失正确停止，当前资产已放在仓库外。历史预期路径为：

- `research/.private-kb-experiments/plan-v1-stage1/frozen.sqlite`
- `research/.private-kb-experiments/plan-v1-stage1/source-metadata.json`
- `research/.private-kb-experiments/plan-v1-stage1/manifest.json`
- `research/.private-kb-experiments/embedding-cache.sqlite`
- `research/ChatGPT/真实查询复用研究-v0.14/queries.json`

这些资料必须对应原始 1,213 个片段、修订 1216、BGE-M3 dense1024 和缓存的 48 个查询向量。不得用合成样本补足正式诊断，也不把私有逐情形输出放入公开仓库。

本轮停在“两门完成，固定配置未观察到剪枝潜力”。原协议、第二部分资料及前轮工程结果保留。正式重放已形成新报告；在线停止未启用，进入下一部分前仍须先评审证据。
