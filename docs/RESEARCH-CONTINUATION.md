# Follow-on stage-three research: 3.5–3.9

[English](RESEARCH-CONTINUATION.md) | [简体中文](RESEARCH-CONTINUATION.zh-CN.md)

This curated research note records decisions and evidence from 30–31 October 2026. It excludes private corpora, queries, vectors, credentials and device-specific information. It is a selective account, not the original experiment archive or a complete reproduction package. Consult later repository material for subsequent developments.

## Mechanism and evaluation readiness (3.5)

The strong comparison must receive ordinary shared scoring, deduplication, caching and cursor continuation. Existing version-dependency repair also belongs to the baseline. Cross-query score evidence warranted a bounded qualification study, not an immediate novelty claim. A review of 12 development families prepared annotation work but did not establish a judged relevance pool. Unjudged items are not negatives; incomplete pools support pooled recall rather than exhaustive recall. No new performance experiment or formal semantic gain was established here.

## Score-transfer qualification (3.6)

Let a be an anchor query, q the current query, s = a·x an already paid score, p the known coordinates x_I, and b an upper bound on the remaining norm ||x_R||. The proposed bound is

`U_B = s + (q_I − a_I)·p + b ||q_R − a_R||`.

It is the λ=1 member of `U_λ = λs + (q_I − λa_I)·p + b ||q_R − λa_R||`. Exact coordinates and anchor scores additionally constrain the residual to a ball intersected with a hyperplane, allowing a tight real-valued bound for that stated information set. Tighter bounds need not minimize runtime or lifecycle cost: compute, summaries, invalidation, matching and coverage must be accounted for. Bounds over previously visited candidates do not certify the unvisited complement. Machine-safe exclusion needs a conservative numerical error chain.

The accepted decision retains the candidate as an optional baseline filter, not a demonstrated independent architecture. This was an analytical study, not a performance benchmark. Related work includes [QCache](https://openproceedings.org/2009/conf/edbt/FalchiLOPR09.pdf) and [Schubert's cosine bounds](https://arxiv.org/abs/2107.04071); neither supplies a machine certificate for this implementation.

## Shared-workflow example (3.7)

A small fictitious-integer fixture exercised repeated queries, scope completion, updates and later queries. With identical cache keys, dependencies and action order, adding a DAG as a record of lazy evaluation produced no exclusive material-work saving over same-key memoization. The three principal streams required 24, 25 and 24 scores per comparable strategy. Other scoring counts do not establish latency or system-level gains. The result leaves untested different joint action-selection rules, production concurrency, durable recovery and semantic quality.

## Joint action selection (3.8)

One frozen fixture compared local routing, greedy selection and a one-step rollout. Three streams and three strategies yielded 30 completed outputs; these are not 30 independent queries. In the positive stream greedy and rollout returned 693 and 604 data-response bytes in three and two calls, respectively. The 89-byte difference was response framing; distinct returned rows and scoring work were equal. After an update, the corresponding totals were 693 and 764 bytes because an additional prefetched row became invalid; the forced-action stream returned 320 bytes for both.

Across this fixed mixture the two strategies returned 1706 and 1688 data bytes and each paid 18 scores, while planner evaluations were 88 and 594. This demonstrates an action difference with a counterexample, not a net total-cost or latency win. Budget interruption and update repair occurred in the fixture; real I/O, mature ANN, semantic quality and production concurrency were not validated.

## Backend action mapping (3.9)

Inspection of the research prototype found that loading a snapshot incurs cost, but after binding, canonical vectors can be gathered by known positions and source rows are resident. The fixed overlapping-page and remote-response framing assumptions in 3.8 do not describe that path, so its byte difference cannot be transferred as a measured benefit. A document-ID batch interface would still need identity, version and scope checks. A batch call neither resolves unknown candidate discovery nor establishes a single physical I/O. No new private-data probe or performance run was performed.

The decision shelved migration of the fixed-page cover candidate to that prototype while preserving the controlled example. Unknown-candidate expansion, scope, invalidation and budgeted action selection remain research questions.

## Interpretation

Formal semantic measures remain unavailable pending reviewed labels and an appropriate judgment pool. Independent implementation re-review of the historical scope-v2 repairs is outstanding. These results do not establish novelty, formal semantic improvement, large-scale performance or a generational advance. Restricted underlying assets are not published here, so the historical experiments cannot all be independently reproduced from this note.
