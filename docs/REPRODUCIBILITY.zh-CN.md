# 公开简查与复现说明

[English](REPRODUCIBILITY.md) | [简体中文](REPRODUCIBILITY.zh-CN.md)

我将可直接执行的机制简查和依赖私有数据的性能实验分开公开。已记录环境为 Python 3.13、NumPy 2.5.4、scikit-learn 1.9.1、USearch 2.26.6。

在仓库根目录运行：

```sh
python -m pip install -r requirements.txt
python "research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py"
```

这些脚本构造虚构向量和临时 SQLite，不需要私人正文或嵌入凭据。部分脚本会覆盖同目录的检查汇总，首次公开记录可从 Git 历史恢复。简查通过不代表复现了私有库耗时，也不代表验证了断电恢复。

历史回放脚本依赖原工作区结构、私有冻结语料、问题文件和已缓存嵌入，这些输入没有上传。输入缺失时不能自行下载替代模型或改成 API 补齐。因此公开仓库支持机制简查，但暂不支持外部独立复现全部私有性能数字。

正式语义实验继续默认使用硅基流动 BAAI/bge-m3 dense1024，不添加 BGE-v1.5 查询前缀。虚构小向量只用于几何或状态检查，不构成嵌入模型对照。日常评分和未来严格认证必须分别遵守各自契约。

发布清单保留来源与公开副本哈希，文档编辑与代码、数据变化分开记录。历史报告指向未公开输入时，链接表达的是来源关系。引用实验结果前，请核对报告日期及代码哈希。
