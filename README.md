# SERA — Stateful Execution for Retrieval Architectures

[English](README.md) | [简体中文](README.zh-CN.md)

**Frontier research on novel retrieval architectures: sparse activation, state reuse, and predictive prefetching.**

SERA studies whether retrieval, candidate reuse, update repair, and predictive work can share versioned execution state and a resource ledger to reduce repeated work while preserving quality and freshness. It starts with personal knowledge bases and aims to investigate larger-scale retrieval.

## Status · 2026-10-29

Research prototype. Stage 2 and stages 3.1–3.2 are delivered; stage 3.3 has a protocol but has not been implemented. Expert-model training remains paused. Predictive prefetching and strict certification are planned research, not shipped capabilities.

The current private benchmark contains 1,213 chunks, 114 sources and BGE-M3 dense 1,024-dimensional embeddings. Stage 3 replays use 16 development query families (48 unique texts, including 32 rewrites); repeated runs are not independent new samples. Semantic labels remain unreviewed.

| Observation | Evidence and limitation |
|---|---|
| Compact candidate layout | C50 merge latency: 7.517 → 4.006 ms versus the JSON implementation (~46.7% reduction). This is an engineering comparison, not an ANN speedup claim. |
| Seed-guided IVF | At 16 partitions / 256 total scores, average exact-vector top-10 overlap: 84.375% → 97.8125%. Worst query remains 80%, and latency increases. |
| Strong baseline comparison | Stable net advantage over mature ANN or the best available cold-IVF configuration has not been demonstrated. |

No demonstrated generational advance, formal semantic improvement, large-scale result, or strict floating-point certificate is claimed.

## Navigate

- [Roadmap](ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md)
- [Results and limitations](docs/RESULTS.md) · [Reproduction](docs/REPRODUCIBILITY.md)
- [Research archive](research/ChatGPT/总体计划执行-v1/执行总纲.md)
- [Publication scope](docs/PUBLICATION.md) · [Changelog](CHANGELOG.md)

## Run the public mechanics checks

Python 3.13 was used for the recorded experiments. From the repository root:

```sh
python -m pip install -r requirements.txt
python "research/ChatGPT/总体计划执行-v1/阶段二/check_framework.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-候选复用/check_candidate_engine.py"
python "research/ChatGPT/总体计划执行-v1/阶段三-紧凑缓存与IVF/checks.py"
```

These checks use fictitious vectors and temporary SQLite databases; they do not need an embedding API or private documents. They write check summaries beside their scripts. Private benchmark runners require assets excluded from this repository; see reproduction notes before running them.

## Research discipline and reuse

Protocols, counterexamples, negative results, setup costs, seed costs, maintenance and fallbacks are retained. Vector top-K overlap is distinct from semantic relevance. Each part is reviewed before the next part starts.

No open-source license has been selected for this initial research archive. Public visibility is not a general grant to reuse the work. Third-party references and dependencies retain their respective terms. Citation is appreciated: cite a specific commit and the relevant report, and distinguish the user's research direction, model-assisted proposals, and experimentally verified observations.
