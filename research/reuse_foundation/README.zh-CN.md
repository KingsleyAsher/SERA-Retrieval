# 检索基础机制复用实现

[English](README.md) | [简体中文](README.zh-CN.md)

我把知识库和记忆项目中可复用的来源校验、失效处理及资源调度机制，落实为独立的 SERA 工程模块。这里的交付不改变冻结实验，也不表示第三阶段第三部分已启动。专家训练、预测预取和多视图实验继续保持原状态。实测与局限见[交付报告](REPORT.zh-CN.md)。

## 模块边界与数据约定

在仓库根目录运行，依赖沿用 `requirements.txt`，本次验证环境为 Python 3.12。没有增加运行依赖。`common.py` 直接调用未修改的阶段二账本、规范评分与 USearch 构建实现；新数据库仅使用 `reuse_*` 表，误将插件原库指定为目标时，会在更改 journal 模式前拒绝打开。

| 接口 | 作用 |
|---|---|
| `export_source(kind, path)` | 只读显式指定的知识库导出目录或记忆数据库，返回规范记录及来源清单 |
| `import_snapshot(records, store, ledger=None)` | 整批验证输入、建立独立快照并返回导入与资源记录 |
| `FoundationStore.apply_events(events, ledger=None)` | 原子回放具有固定身份的变更事件，拒绝冲突重试 |
| `capture_dependencies` / `validate_dependencies` | 绑定来源、权限、表示、生命周期和存储身份；完整查询额外绑定目录代次 |
| `Baselines.run` | 执行精确扫描或 ANN 加规范重排，返回覆盖、累计成本和接续状态 |
| `Resources.run_shared` | 合并相同依赖的字节计算；回调自行向父账本记录其实际工作 |
| `run_checks()` / `run_benchmark()` | 分别执行合成正确性检查或独立进程基准 |

每条记录必须有 `namespace`、`id`、`version`、`text`、`content_sha`、`path`、`scope`、`visible`、`status`、`policy_revision` 和 `preprocessing`。正文哈希采用 UTF-8 SHA-256。状态可为 `active`、`pending`、`withdrawn`、`superseded`、`deleted`。向量可缺失；存在时必须声明模型、维度和 `float32`／`float64` 类型。`provenance` 保存来源依据。坏记录导致整批失败，不补模型、不自动截断。

一次导入表示所含命名空间的**完整来源快照**，遗漏的旧成员转为不可见墓碑。空来源必须在 `source_manifest.namespace` 中明确身份。完全相同的导出重试返回原导入回执，不覆盖之后的更正或删除；确需恢复时，要提供新的权威来源版本或显式事件。相同向量字节可以共享不可变载荷，但来源身份、正文和适用状态分别保留。

FP32 输入先保留小端原始字节哈希，再提升到 float64 并重新归一化；转换标识与原实验隔离。原始 float64 输入必须已满足现有规范，不自动改写。模型、预处理、维度、转换契约不同的记录不能混在一次向量查询中。查询使用规范化 float64 向量，命令行默认仅访问 `global` 范围。

## 两种来源怎样接入

知识库适配器读取显式目录下原生的 `manifest.json`、`catalog.json` 和被引用的 `vectors-N.bin`。原生 catalog 没有完整正文和权限事实，因此额外要求 `source-map.json`，字段如下：

```json
{
  "format": 1,
  "namespace": "explicit-library-identity",
  "policy_revision": "explicit-policy-version",
  "model": "BAAI/bge-m3",
  "preprocessing": "explicit-model-input-and-chunk-contract",
  "documents": {
    "notes/example.md": {
      "text": "explicitly exported complete source text",
      "revision": "the catalog revision",
      "content_sha": "SHA-256 of text",
      "visible": true,
      "status": "active",
      "scope": "global"
    }
  }
}
```

适配器核对正文哈希与 catalog 版本，按 JavaScript UTF-16 单元解释分块位置，重建模型输入哈希，验证已有向量的 slot、长度和 checksum。没有向量映射时保留待构建状态；已有向量却缺 checksum 时拒绝，不替旧格式静默修复。导出期间文件身份、大小或纳秒时间变化会使整批失败。来源映射是调用者明确提供的导出，不是独立核验的事实或实时权限服务；权威来源改变后需要重新导出。

记忆适配器对指定 SQLite 使用 `mode=ro` 和读事务，能读取 WAL 中已经提交的数据。它处理原生 `plugin_memory_entries`、来源控制，以及存在的 claim／待更新表；全局与项目范围不混用，排除和删除的来源不可访问，更正待定、撤回与被替代均保留状态。没有抽取或嵌入调用。插件记录通常没有向量，导入后仍只是一份有来源和状态的记录集，不自动获得语义检索。命名空间由数据库的解析后路径生成，移动后的副本视作另一来源。SQLite 可能管理 WAL 共享内存边车文件；适配器不写来源数据或表结构。

`fixtures.py` 生成两种原生格式的虚构样例。本轮没有安装真实插件，也没有导出私人资料。

## 失效、预算与接续

事件包含 `event_id`、`namespace`、`id`、`action`。`change`／`correct` 提供同一身份、不同版本的完整 `record`；`permissions` 提供新 `policy_revision`、`visible`，可选更新 `scope`；其他操作为 `withdraw`、`delete`、`pending`、`activate`。一批事件共同提交；普通失败整批回滚，但已经发生的账本消耗不退款。

快照保留历史状态，访问权限始终按当前来源复核。当前查询只选有效记录；历史查询返回旧状态时，输出同时标明快照 `status` 和 `current_status`。删除会阻止本接口继续访问历史内容，但不代表安全擦除 SQLite 历史页或已导出的文件。

单条派生工作的依赖戳允许无关条目变化后继续使用。完整 top-k 查询额外绑定整个目录代次，因为新增竞争项也可能改变结果。所有来源变更与代次递增在同一事务完成。序号还能防止“有效→撤回→有效”把旧任务重新变成合法结果。异步任务在缓存填充和返回前验证依赖；最后一个等待者取消后，即使回调吞掉取消信号，也不能发布结果。若仍有其他有效等待者，公共计算可以完成。

缓存预算按键与字节载荷计量，不是 Python 堆或进程内存上限。超预算只影响保留，不缩小搜索范围。后台工作串行执行，在显式批次检查点让出前台；回调必须实际调用检查点，原生同步 ANN 内部无法抢占。本轮没有自动预取或预测器。

精确路径逐窗计算规范 float64 内积，以稳定数字 ID 处理同分，只保留有界 top-k。ANN 使用未修改的 USearch 构建方法，并按同一规范重排。每个基线对象最多保留一个原生索引；其矩阵和原生分配在字节缓存预算之外，另测进程内存。评分与逻辑向量读取在批次发起前统一准入。预算耗尽时保存评分／来源游标、已有分数及累计消耗，正常恢复不重复评分；接续载荷必须与已提交状态一致。若提交额度本身不足，结果会明确标记未持久化，不能把这份未提交状态当作可恢复凭据。

不支持的硬上限会被拒绝，原生 ANN 距离次数和访问数只作观测。逻辑向量字节包含缓存供给的数据；缓存读取字节另作观测，不是 SSD 物理流量。元数据物化、SQLite 页面访问和任意回调 CPU 耗时不构成硬物理 I/O／CPU 限制。断电恢复、物理恰好一次以及跨插件／SERA 数据库原子事务均不在本轮声明范围。

## 运行与资料索引

```sh
python -m research.reuse_foundation checks --output /tmp/reuse-checks.json
python -m research.reuse_foundation benchmark --output /tmp/reuse-benchmark.json
python -m research.reuse_foundation.verification --output /tmp/frozen-regressions.json
python -m research.reuse_foundation export --kind knowledge --source /explicit/bundle --output /tmp/export.json
python -m research.reuse_foundation export --kind memory --source /explicit/memory.sqlite --output /tmp/memory-export.json
python -m research.reuse_foundation import --input /tmp/export.json --store /tmp/reuse.sqlite
python -m research.reuse_foundation events --input /tmp/events.json --store /tmp/reuse.sqlite
python -m research.reuse_foundation query --store /tmp/reuse.sqlite --vector /tmp/query.json --output /tmp/result.json
```

可通过 `--limits '{"canonical_scores":7}'` 制造中断，再用 `--resume <committed-signature>` 和足够的累计额度恢复同一请求。范围、快照、后端、k、窗口大小不能中途更换。命令行打印简短回执，正文与证据只写指定输出。真实导出、向量及数据库应保存在版本控制之外。

共享代码清单：`common.py` 连接冻结契约，`sources.py` 负责来源，`store.py` 负责快照和事件，`runtime.py` 提供依赖／缓存／调度／发布，`baselines.py` 实现基线；另有 `fixtures.py`、`test_foundation.py`、`benchmark.py`、`verification.py` 及包入口。`results/` 保存合成检查、基准和隔离回归记录，`provenance.json` 固定上游身份及新增代码／结果哈希，`licenses/*-MIT.txt` 保留上游许可原文。本轮为 Python 机制实现，借鉴的工程模式不等于已经接入真实插件；来源归属和验证结论分别记录。
