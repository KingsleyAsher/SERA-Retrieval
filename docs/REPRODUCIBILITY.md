# Reproducing the public checks

[English](REPRODUCIBILITY.md) | [简体中文](REPRODUCIBILITY.zh-CN.md)

I publish executable mechanics checks separately from private-data performance evidence. The recorded environment used Python 3.13, NumPy 2.5.4, scikit-learn 1.9.1 and USearch 2.26.6.

From the repository root:

```sh
python -m pip install -r requirements.txt
python "research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py"
```

These scripts create fictitious vectors and temporary SQLite stores. They require neither private documents nor embedding credentials. Some write summaries beside their scripts; Git history retains the originally published summaries. Passing them does not reproduce private benchmark timings or establish power-loss recovery.

Historical replay scripts expect the original workspace layout, a private frozen corpus, query files and cached embeddings. Those inputs are intentionally absent. A missing input is not an invitation to download another model or silently call an API. The public repository is therefore sufficient for the small mechanics checks, but not for independently reproducing every private-data performance number.

My default semantic embedding service remains SiliconFlow BAAI/bge-m3 dense1024 without a BGE-v1.5 query prefix. Tiny synthetic vectors are geometry fixtures, not model comparisons. The daily scoring contract and future exact-certification contract must not be interchanged.

The publication manifest records source and publication hashes. Editorial changes are tracked separately from code and data. Archival links to excluded inputs are historical provenance references. Consult each report's date and code hash before associating it with a result.
