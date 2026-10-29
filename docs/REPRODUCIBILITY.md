# Reproduction / 复现

Install `requirements.txt` using Python 3.13. From repository root:

```sh
python "research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/review_fix_probes.py"
python "research/ChatGPT/总体计划执行-v1/阶段二/check_review_boundaries.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py"
```

Mechanics checks construct fictitious vectors, do not need API credentials, and may overwrite their adjacent generated check-summary files. They do not reproduce private-data performance or certify production correctness. The original historical checks are preserved in Git history.

Historical runners are archival scripts, not turnkey public benchmarks: they expect the original project layout, a private frozen snapshot, cached embeddings, and excluded query files. Do not run them expecting the private benchmark to download. Public documents and summaries allow inspection of protocols and reported outcomes; underlying private performance data are not independently reproducible from this repository alone.

Published source copies retain hashes in `PUBLICATION-MANIFEST.json`; absolute local paths are redacted where present, so source and publication hashes may differ. References to excluded review inputs or private artifacts in archival reports are historical references, not promises those files ship here. Research summaries describing old code hashes remain tied to those old versions.

Default future semantic experiments use SiliconFlow BAAI/bge-m3 dense1024, without a BGE-v1.5 query prefix. No API client or key is required for the public checks. The tiny vectors are geometry fixtures, not alternative embedding-model comparisons.
