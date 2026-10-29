# Architecture / 架构

The executor represents requests (vector, scope, snapshot, scoring contract, quality target, budget), actions (rescore, expand, scan, rerank, fetch source, repair), and resumable state (candidates, frontier, dependencies, consumed resources, pending work).

The current reference implementation uses Python and SQLite metadata, full float64 inner-product scoring, USearch candidates with canonical reranking, and Chinese lexical/vector hybrid retrieval. The stage 3.2 reference IVF exposes posting-list and scoring cursors. Valid seeds are rescored for the current query and consume the same total score/read budget as new scans.

Result categories reserve approximate, probabilistic, certified, pending and rejected states. Reserved types do not imply implemented guarantees. Source verification currently checks frozen snapshot content, not live original-file authenticity. Native ANN calls cannot enforce arbitrary internal hard budgets midway through a call.

Next correctness constraints: opening a partition is not completing it; unfinished active tails and pending scores must remain covered; seed vector reads and scores require atomic admission; filters and bound coverage require separate dependency validation. Stage 3.3 is not implemented.

The daily path and the future strict stored-FP32 real squared-L2 contract remain separate. Ordinary float64 geometric diagnostics are not machine-verified certificates.
