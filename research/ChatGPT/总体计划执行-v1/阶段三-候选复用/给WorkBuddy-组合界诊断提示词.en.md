# Research brief: diagnose the value of combined block bounds

[English](给WorkBuddy-组合界诊断提示词.en.md) | [简体中文](给WorkBuddy-组合界诊断提示词.md)

I want to know whether the sphere/subspace maximum has useful pruning potential on the fixed BGE-M3 geometry before adding residual quantization or more architecture layers. Start with a general center and a radius/statistics set that covers every legal block member.

State `LB_sphere=max(||q−c||−ρ,0)^2` and the orthogonal-subspace norm-range lower bound, justify the maximum, and distinguish real-arithmetic validity from conservative machine evaluation. Unit vectors do not imply unit centroids. Neither bound may be assumed universally stronger. Use explicit counterexamples for incorrect simplifications.

The planned blocks are 16/64; the identity-coordinate reference should precede PQ/OPQ. Keep stored-FP32 real squared L2 separate from the daily float64 inner-product score. An offline exact top-K threshold is a diagnostic upper opportunity, not a free online candidate threshold. Legal online supports must be distinct and version/scope compatible.

Specify bound tightness, sphere-only/stat-only/both/neither categories, denominators, metadata size, build/planning cost and update invalidation. Count only still-unscored unique members as potentially avoidable work; already paid seeds cannot be saved twice. Finite zero violations do not establish a numerical certificate.

Deliver a limited diagnostic protocol, assumptions and counterexamples. Do not claim existing speedup, restart expert training, expand scale, introduce nonidentity OPQ or rewrite the whole system. A failed bound configuration narrows that mechanism, not the complete research direction.
