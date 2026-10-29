# Architecture and execution contracts

[English](ARCHITECTURE.md) | [简体中文](ARCHITECTURE.zh-CN.md)

I treat retrieval as a sequence of paid, resumable actions. A request binds the query vector, filter scope, snapshot, scoring contract, quality target and resource limits. Its state records candidates, scores, backend continuation data, dependencies, completed actions and cumulative consumption.

The reference implementation uses Python and SQLite. Backends include full float64 inner-product scoring, USearch candidate generation followed by canonical reranking, and Chinese lexical/vector hybrid retrieval. Stage 3.2 adds a controllable IVF backend. Valid old candidates are rescored for the current query before they influence partition priority. Their reads and scores consume the same total budget as new scans.

The ledger distinguishes model/network work, local computation, logical reads, cache storage, initialization, maintenance, source access, commits and fallback. Resuming or falling back does not create a new allowance. Known action costs are admitted atomically before execution. Native ANN work can be observed after a call, but unsupported internal hard limits are rejected rather than advertised as enforced.

The result interface reserves approximate, probabilistic, certified, pending and rejected states. Reservation is not implementation: the daily path currently provides no strict certificate or inherited probability guarantee. Source checks verify materialized snapshot text; they do not prove that the original filesystem file was independently authenticated.

For the next part, I distinguish partition scheduling from unfinished-region coverage. An opened posting list is not a completed partition. Active tails and enumerated-but-unscored items must survive checkpoints. Only scoring completion can discharge their outstanding work. This is a protocol requirement, not a claim that stage 3.3 already runs.

Daily normalized float64 inner product and the future stored-FP32 real squared-L2 certification contract remain separate. Ordinary floating-point geometric diagnostics cannot bridge that distinction without an explicit numerical argument.
