"""Aggregate already completed fixed replay; does not run experiments."""
from pathlib import Path
import json,hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    r=json.loads((HERE/'results-summary.json').read_text(encoding='utf-8'))
    private=ROOT/'.private-kb-experiments/plan-v1-stage3-candidate'/r['run']
    raw=json.loads((private/'raw-results.json').read_text(encoding='utf-8'))
    assert len(raw['requests'])==4800 and len(raw['prewarm'])==960 and len(raw['fill'])==576
    assert len({(x['rep'],x['trace_index'],x['arm']) for x in raw['requests']})==4800
    assert all(x['resources']['consumed']['source_reads']==10 for x in raw['requests'])
    assert all(x['resources']['consumed']['state_commits']==1 for x in raw['requests'])
    assert hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()==r['protocol_sha256']
    for name,digest in r['code_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest
    a={x['label']:x for x in r['aggregate']};base=a['ann50-ef128']
    labels=['ann50-ef128','full','seed-ann-C10','seed-ann-C50','seed-ann-C200',
            'merge-ann-C10','merge-ann-C50','merge-ann-C200','fresh60-ef128','fresh100-ef128','fresh250-ef128']
    table=['| 路径 | 改写前十平均重合 | 最差改写 | 平均耗时 ms | P95 ms | 规范计分项 | ANN 内部距离数 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for label in labels:
        x=a[label]
        table.append(f"| {label} | {100*x['rewrite_overlap']['mean']:.3f}% | {100*x['rewrite_overlap']['minimum']:.0f}% | {x['rewrite_ms']['mean']:.3f} | {x['rewrite_ms']['p95']:.3f} | {x['resources']['canonical_scores']['mean']:.2f} | {x['resources']['ann_distance_evaluations']['mean']:.2f} |")
    lifecycle=['| 路径 | 普通锚点预热 ms | 候选填充 ms | 候选写入 ms | 全工作流累计 ms |',
               '|---|---:|---:|---:|---:|']
    for label in ['ann50-ef128','full','seed-ann-C200','merge-ann-C10','merge-ann-C50','merge-ann-C200','fresh250-ef128']:
        x=a[label]
        lifecycle.append(f"| {label} | {x['prewarm_ms']:.1f} | {x['candidate_fill_ms']:.1f} | {x['candidate_write_ms']:.1f} | {x['lifecycle_ms']:.1f} |")
    failures=[]
    for C in (10,50,200):
        selected=[x for x in raw['requests'] if x['arm']==f'seed-ann-C{C}' and x['rep']==0 and x['variant']>0 and not x['repeat']]
        failures.append(f"- C={C}：32 条不同改写中，{sum(x['overlap']<.9 for x in selected)} 条低于 90%，{sum(x['overlap']==1 for x in selected)} 条完整覆盖前十。")
    extra=[]
    for C in (10,50,200):
        x=a[f'merge-ann-C{C}'];delta=(x['rewrite_ms']['mean']/base['rewrite_ms']['mean']-1)*100
        extra.append(f"- 合并 C={C} 相对 ANN50 平均耗时增加 {delta:.1f}%；三次回放的改写均值均更慢。ANN 内部距离数仍为 {x['resources']['ann_distance_evaluations']['mean']:.3f}。")
    report='''# 阶段三首部分：候选复用消融报告

日期：2026-10-29。状态：本部分执行完成，等待用户审查；不自动开启下一部分。

## 结论和退出判断

当前“旧候选重新评分”和“旧候选与完整新 ANN 合并”均未取得可重复净收益。候选直接返回没有通过预注册的最低质量条件；合并路径与 ANN 基线在这组查询上同为 100% 向量前十重合，但增加耗时和初始化/填充成本，未减少新 ANN 的内部距离计算。没有达到至少一项主要成本降低 20% 且质量达标的挑战目标。

按原计划收窄：当前 JSON 候选扫描＋重新评分／候选合并不作为默认路径，保留实现、失败记录与诊断数据。这个结论限当前语料、查询和实现，不否定缓存、稀疏激活、预测或联合架构整个方向。

这次的实质产出是：把候选复用接入共享快照、过滤、来源、预算和接续状态，形成可复现的失败定位；尚无创新、领先或代际提升结论。

## 协议、工作量和质量边界

- 用户本轮明确授权阶段三首部分。协议和执行代码哈希在结果产生前记录于 `启动清单.json`；未按结果扩大参数矩阵。
- 固定 1,213 个实际片段、114 来源、修订 1216；BGE-M3 dense1024 归一化向量。只读使用隔离副本，未读取凭据或训练目录，新增 API 调用为 0。
- 20 个配置 × 3 次回放 × 每次 80 个请求，共 4,800 个测量请求；另有 960 个普通 K10 锚点预热请求、576 个完整 K=C 候选填充请求，合计 6,336 个检索请求；576 次候选写入另计资源。
- 只有 48 个已有开发查询：16 个锚点及其 32 个改写。重复回放不是新增独立样本；未触碰封存测试族，未用人工标签作正式语义结论。
- 下表仅取每轮首次出现的 32 个改写，三轮共 96 次观测；表中“前十重合”比较完整规范 f64 向量评分，不能当语义准确率。
- 门槛预定为改写最小重合率及 P10 均不低于 90%；概率保证、严格认证、语义非劣均未建立。

## 主结果

'''+ '\n'.join(table)+'''

仅旧候选直接返回的失败分布（32 个不同改写，避免把三次重复当 96 个新查询）：

'''+ '\n'.join(failures)+'''

与新 ANN 合并的配对观察：

'''+ '\n'.join(extra)+'''

完整 20 配置的每查询配对差异、三轮分布、ef512 对照、全量填充对照见 `results-summary.json`。ANN 建候选与完整评分建旧候选的直接返回路径，在三个 C 档的改写平均与最差重合均相同；这组缺漏不能简单归咎于 ANN 旧候选不够精确。精确旧 top-C 不构成新查询召回上限。

## 收益为什么没有出现

1. **合并没有热启动搜索。** 本次新 ANN 仍从原入口完整搜索，平均内部距离计算 606.625 次；合并只是额外候选与去重评分。因此不能把它称为搜索热启动或声称节省 ANN 访问。
2. **当前布局开销很大。** 候选缓存存序列化 JSON，匹配时解码 16 个旧查询向量与条目，每个改写逻辑读取约 353–384 KB；候选匹配平均约 3.44–3.96 ms，而 ANN50 搜索约 0.293 ms。它们不是固有算法下界；二进制常驻布局能否改进总成本，本轮未实现或测量，不能从减去计时项推算“优化后收益”。
3. **旧候选覆盖与查询相似不是一件事。** 32 个改写均选中对应锚点家族，但 C200 仍有 3 条低于 90%。平均 96.25% 不能保证单个请求；本轮没有校准模型来在线判断这些失败。
4. **共有提交成本很重。** ANN50 的数据库提交平均约 2.478 ms，总耗时约 4.179 ms。共有来源读取、状态序列化、事务提交并未因命中候选而消失。每查询 FULL 提交是当前参考执行政策，不是所有生产检索必须承担的固定成本。

原生 ANN 距离数与 f64 规范评分是不同操作，不能直接相加。候选缓存逻辑读取不能与未知的 ANN 内部物理读取直接比较。prepare 包含 ANN 和匹配子计时，不能再将这些子项重复加总。

## 初始化、工作流总账和缓存

'''+ '\n'.join(lifecycle)+'''

上表为三次独立缓存回放的实际累计时间，包括普通预热、完整候选填充、写入、测量请求及逐臂执行器构建。普通预热含每臂索引构建，故计入有限工作流后，全扫参考的累计成本可低于 ANN；不能据此推广到长寿命大库。

公共输入读取约 49.8 ms、隔离库导入约 77.6 ms、快照物化约 35.2 ms，单独计入公共准备账，不重复摊入每臂。公共查询嵌入缓存读取约 5.93 ms；未测无缓存时模型与网络耗时，也不宣称这些成本为零。

每臂均提供 32 项／4 MiB 普通结果 LRU，候选容量上限为 16 项／4 MiB。候选实际序列化载荷约 353–384 KB（未计 Python 对象、分配器、位置字典内存）。各臂普通结果命中均为 123/240，即 51.25%；其中每轮有 32 次人为紧邻重复。本实验不能估计自然命中率，也没有证明候选机制提高了普通结果缓存命中率。缓存命中仍读取 10 项来源并提交一次状态。

此处各缓存职责不同：查询嵌入缓存只报告现有 48 输入命中；候选缓存报告兼容、匹配与新查询前十覆盖；来源层为共同物化快照，没有独立正文缓存命中实验。未将“来源读取来自内存”记成一个新算法收益。

## 正确性简查和未验证范围

10 项虚构夹具检查通过，覆盖：选中条目／验证游标落盘接续、计分接续不重跑 ANN、空桶回退共用父预算、原生 ANN 内部硬预算拒绝、过滤桶隔离、普通缓存命中仍付来源和提交成本、排除自身后空桶、失效 ID/版本、规范排序、新快照删除隔离和旧快照显式绑定。

实际回放完成后核对了请求数量、配对键唯一性、每请求来源与提交计数，以及协议和源文件哈希。阶段二实现未改写，旧实验记录保留。这里不是全部软件行为的证明。

原文件真实性、物理 IO／WAL 放大、进程 RSS、并发、断电恢复、跨更新候选复用、自然话题跳变和大规模负载均未验证。源验证只绑定物化快照内正文。A05 跨 K 复用与 E03 多层副本淘汰尚未实现为通用能力。

## 下一部分建议，尚未执行

先把候选匹配改为可公平共享的紧凑常驻布局，并在可控制访问前沿的 IVF 参考后端比较“冷启动、相同布局普通缓存、实际热启动”；以访问数、候选补齐和总成本判断是否有复用增量价值。不能只优化 JSON 后就称架构成立，也不继续在同一开发查询上无限调参。

DeepSeek 可给出至多两种真正改变访问队列和停止动作的机制及反例；WorkBuddy 可给出组合下界的有效条件与无效几何诊断。两方本轮只写规格与证据需求，不改本实现、不运行主实验、不启动训练或认证阶段。独立任务提示词另存于同目录。

本部分到此停止，等用户审查后决定下一步。
'''
    (HERE/'阶段三首部分报告.md').write_text(report,encoding='utf-8')
    statepath=HERE.parent/'执行状态.json'
    state=json.loads(statepath.read_text(encoding='utf-8'))
    state.update(stage3_delivery='part1_ready_for_review',stage3_part1_completed=True,
        stage3_part1_run=r['run'],stage3_part1_main_requests=4800,stage3_part1_total_search_requests=6336,
        stage3_part1_correctness_checks=10,stage3_part2_started=False,user_confirmation_required_for_stage3_part2=True,
        quality_labels='unreviewed',stage3_part1_outcome='no_net_benefit_for_current_seed_only_or_candidate_merge')
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=dict(stage='3.1',status='part1_ready_for_review',protocol_sha256=r['protocol_sha256'],
        code_sha256=r['code_sha256'],private_run=str(private),public_files=['protocol.json','candidate_engine.py',
        'check_candidate_engine.py','checks.json','run_ablation.py','results-summary.json','阶段三首部分报告.md'],
        raw_private=True,new_api_calls=0,expert_training=False,part2_started=False)
    (HERE/'交付清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(report=str(HERE/'阶段三首部分报告.md'),checked_requests=4800,part2_started=False),ensure_ascii=False))


if __name__=='__main__':main()
