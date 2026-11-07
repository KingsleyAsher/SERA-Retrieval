# Follow-on mechanics artifacts

[English](README.md) | [简体中文](README.zh-CN.md)

These historical artifacts accompany the [stage 3.5–3.9 note](../../docs/RESEARCH-CONTINUATION.md). They preserve the original Python reference code, fictitious integer fixtures, and recorded JSON results for stages 3.7 and 3.8. They do not contain private inputs or establish semantic quality, real I/O performance, or architectural superiority. The policy attribution is a reconstruction from the recorded actions, not another run. `provenance.json` records SHA-256 of the unchanged selected files; omitted historical governance records are not included.

Run `python research/stage35_39_mechanics/verify.py` from the repository root. The standard-library-only verifier imports each original module, executes its `run_flow` function on the included fictional fixture, normalizes the result through JSON, and compares the 12 workflow and 9 policy runs with the recorded `runs` arrays. It also checks the selected artifact hashes. It does not overwrite the historical results, run the original guarded `main` entry points, contact any service or measure performance. The original entry points expected a frozen governance layout that is not part of this public selection.

Workflow comparisons, pending/resume checks and policy action-accounting scope are described in the research note. The fixtures are constructed examples, not sampled users, natural workloads or semantic ground truth.
