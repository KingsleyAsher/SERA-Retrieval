# Scope-v2 correction and independent-review entry point

[English](README.md) | [简体中文](README.zh-CN.md)

This selection supplies the historical scope-v1 counterexamples, scope-v2 implementation and fictional checks for an independent review of the corrected version. **Independent implementation re-review remains outstanding.** Author checks and the publication-time replay below are not a substitute.

## Review targets

The corrected [scope engine](阶段三第四部分定点修订-2026-10-30/scope_engine.py) has source SHA-256 `fd6b28bbe6ee00cfd75259ee4bf553db9a9c2881c494a7a55bd27c27a39fb3cd`. The [scope-v1 engine](阶段三-合法范围成本诊断/scope_engine.py) provides the defect comparison. Both use the included [historical framework](阶段二/framework.py), whose source hash matches the correction manifest's declared dependency.

Each selector has one publication change: its private-directory default is disabled and callers must explicitly set an isolated fixture directory. The selection algorithms are otherwise preserved. [Provenance](provenance.json) records source and publication hashes. The [contract](阶段三第四部分定点修订-2026-10-30/修订契约.json) and before/after probe results contain fictional cases only.

## Review questions

The original completion path could persist `commit` despite returning a completed result, causing restored work to request commit budget again. The correction serializes a terminal copy and updates in-memory state only after a successful save. Budget denial or an observed SQLite write lock must not create a false terminal record; issued save attempts remain charged. Tested recovery covers the same request and snapshot with valid dependencies; it does not establish exactly-once behavior for arbitrary crashes or uncertain commit outcomes.

The original scope threshold mixed integer truncation with an implicit minimum of ten members. The corrected selector uses `total > 0`, `10*count >= total`, and `4*count <= 3*total`, with integer distance to half. Valid small scopes must remain eligible.

Historical checks recorded both counterexamples flipping, plus four targeted and six inherited check groups. The original counterexample, correction checks and inherited checks passed when replayed in an isolated temporary copy for publication. This is not an independent review, a private-data replay or a performance measurement. Earlier timings apply to scope-v1 only.

For review, copy this entire directory to a temporary location before running `review-probe-original.py`, `verify_revision.py` and `checks.py`: the latter two write results next to the scripts. They use temporary SQLite and fictional inputs. Dependencies are listed in the repository's root `requirements.txt`. Do not assume production readiness from these checks.
