# Changelog

[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

## 2026-11-07 — Stage-3.3 frozen diagnostic completed

The original private assets are now available externally. All 128 fixed cases completed over 32 different rewrites, with 5,120 block comparisons and no observed raw coverage violations. Every tested bound excludes zero unscored eligible vectors; even the combined-bound oracle diagnostic has zero potential. I retain this negative result without expanding the grid or enabling online stopping. Current-bound/support timings are separated from evaluation work; 13 stage-3.3 and 27 foundation tests pass. Only aggregate evidence is public. See the [completed diagnostic report](research/stage33/REPORT.md).

## 2026-11-07 — Reuse foundations and stage-3.3 first gate

I delivered isolated read-only adapters, versioned snapshots, lifecycle/dependency guards, cooperative resource management and canonical exact/ANN baselines. The foundation passes 27 tests and five historical regression programs. Its synthetic benchmark preserves exact ranking with lower peak memory from windowing; it does not establish a quality-matched ANN or architecture advantage. See the [engineering report](research/reuse_foundation/REPORT.md).

The new stage-3.3 frontier passes ten prerequisite groups and two geometry tests. Its fixed 128-case offline replay is input-blocked, not completed: the original frozen corpus, query file and cached vectors are absent. The [partial delivery](research/stage33/README.md) and canonical execution status record this boundary. Expert training and online bound stopping remain off. Historical executors, protocols and experimental metrics are preserved; current progress metadata is updated separately.

## 2026-10-29 — Bilingual research documentation

I added separately authored Chinese and English editions for the project guides and research archive, together with language navigation and artifact-reading guides. The writing uses my project perspective. Code and canonical data are unchanged. This documentation work does not start stage 3.3 or produce new experimental evidence.

## 2026-10-29 — Initial public archive

I published the execution plan, stage-2 framework and repairs, stage-3.1 reuse experiments, stage-3.2 compact layout and controllable IVF, and the proposed stage-3.3 protocol. The archive retains negative results and strong-baseline limitations. Private inputs and credentials remain excluded. I selected Apache-2.0 for original project code and documentation; third-party terms remain separate.
