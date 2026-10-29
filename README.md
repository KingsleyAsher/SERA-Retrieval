# SERA — Stateful Execution for Retrieval Architectures

[English](README.md) | [简体中文](README.zh-CN.md)

**Frontier research on novel retrieval architectures: sparse activation, state reuse and predictive prefetching.**

I started SERA to explore whether retrieval, candidate reuse, update repair and predictive work can share versioned execution state and a resource ledger. My objective is a better joint trade-off across semantic quality, latency, resource efficiency, freshness and stability, beginning with a personal knowledge base and extending only when evidence supports larger-scale claims.

## Current evidence · 2026-10-29

The common executor and stages 3.1–3.2 are delivered. Stage 3.3 has a protocol but is not implemented. Expert training is paused. Predictive prefetching, learned stopping and strict certification are research directions rather than shipped capabilities.

The private snapshot contains 1,213 chunks from 114 sources with BGE-M3 dense1024 embeddings. Stage-3 diagnostics use 16 development families and 48 unique texts, including 32 rewrites. Semantic labels remain unreviewed.

| Finding | Boundary |
|---|---|
| Compact C50 merging: 7.517 → 4.006 ms versus JSON | A repeatable layout improvement, not a demonstrated ANN speedup |
| IVF16/B256: mean exact-vector top-10 overlap 84.375% → 97.8125% with C200 seeds | Same total scores; worst warm case 80%, with higher latency |
| Strong-baseline comparison | Stable net advantage over mature ANN or the best cold-IVF point remains unproved |

I do not claim formal semantic uplift, large-scale success, validated novelty or a generational improvement from the current results.

## Explore and reproduce

- [Roadmap](ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md)
- [Results](docs/RESULTS.md) · [Reproduction](docs/REPRODUCIBILITY.md)
- [Research library](docs/INDEX.md) · [Code and data guide](docs/ARTIFACTS.md)
- [Publication policy](docs/PUBLICATION.md) · [Language policy](docs/LANGUAGES.md)
- [Licensing](docs/LICENSING.md) · [Citation](docs/CITATION.md) · [Changelog](CHANGELOG.md)

Install `requirements.txt` with Python 3.13 and follow the reproduction guide. The public mechanics checks use fictitious vectors and temporary SQLite, without private documents or API credentials. Full private-corpus performance runs require excluded assets and are not independently reproducible from this repository alone.

I retain protocols, counterexamples, negative results and lifecycle costs. Chinese and English materials are written directly from the same evidence, with language-appropriate structure. Code and numeric records remain canonical shared artifacts. Original project code and documentation use [Apache-2.0](LICENSE); third-party terms remain separate.
