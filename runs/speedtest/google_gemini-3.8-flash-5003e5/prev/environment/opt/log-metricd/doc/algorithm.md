# Logarithmic Quantile Sketch (DDSketch) Specification

## 1. Overview
log-metricd implements a logarithmic quantile sketch algorithm designed to process streaming positive numerical data (e.g. request latencies) and answer percentile queries with provable relative error guarantees under constrained memory budgets.

## 2. Theoretical Relative Error Bound
Let v > 0 be an input sample and v_q be the true q-th quantile. An estimated quantile v_hat satisfies an alpha-relative error bound if:

    |v_hat - v_q| / v_q <= alpha

where alpha in (0, 1) is the maximum acceptable relative error (typically alpha = 0.01 for 1% error).

### 2.1 Derivation of Base Gamma
Values are partitioned into exponentially growing intervals [L_k, R_k) where:
    L_k = gamma^k
    R_k = gamma^(k+1)
for integer bucket index k.

Any sample v belonging to interval [L_k, R_k) is mapped to index k. When reconstructing an estimated value v_hat_k for bucket k, the worst-case relative error occurs at the boundary points L_k and R_k:
    Error at L_k:  (v_hat_k - L_k) / L_k <= alpha  ==>  v_hat_k <= (1 + alpha) * L_k
    Error at R_k:  (R_k - v_hat_k) / R_k <= alpha  ==>  v_hat_k >= (1 - alpha) * R_k = (1 - alpha) * gamma * L_k

Equating the two boundary constraints to minimize the base gamma yields:
    (1 + alpha) * L_k = (1 - alpha) * gamma * L_k
    ==> gamma = (1 + alpha) / (1 - alpha)

Note: Approximating gamma as (1 + alpha) produces a sub-optimal base that fails theoretical error bounds when combined with bucket boundaries.

### 2.2 Bucket Representative Value
For bucket k with lower bound L_k = gamma^k and upper bound R_k = gamma^(k+1), the representative value v_hat_k returned during quantile reconstruction must satisfy the relative error bound uniformly across [L_k, R_k].
Setting:
    v_hat_k = (2 * gamma / (1 + gamma)) * L_k = (1 + alpha) * gamma^k
(or the geometric midpoint gamma^(k + 0.5)) ensures that for any value v in [L_k, R_k]:
    |v_hat_k - v| / v <= (gamma - 1) / (gamma + 1) = alpha

Returning the lower bound L_k directly results in a one-sided relative error up to (gamma - 1) = 2*alpha / (1 - alpha) > alpha, which violates the error tolerance on heavy-tailed distributions.

### 2.3 Numerical Stability and Boundary Precision
Due to IEEE 754 floating-point rounding errors, computing k = floor(ln(v) / ln(gamma)) when v is an exact power gamma^k can evaluate to k - epsilon. Implementations must add an infinitesimal offset (e.g. 1e-12) to ensure exact boundary values map to the correct bucket:
    k = floor(ln(v) / ln(gamma) + 1e-12)

## 3. Dynamic Stream Compaction and Budget Allocation
Each stream i is configured with a dynamic range [x_min, x_max], a target error alpha, a maximum permissible error max_alpha, and an allocation priority.

The uncompacted bucket requirement is:
    B_i = ceil( ln(x_max / x_min) / ln(gamma_i) ) + 1

A global memory budget B_total limits the sum of allocated buckets across all active streams:
    sum(B_i) <= B_total

When the total requested buckets exceed B_total, streams must be compacted to reduce bucket usage:
1. Compaction preserves the full range [x_min, x_max]. Samples within [x_min, x_max] must NEVER be dropped or rejected.
2. Compaction is applied by scaling the logarithmic base by an integer multiplier m in {2, 3, 4, ...}:
    gamma'_i = gamma_i^m
    effective_alpha_i = (gamma'_i - 1) / (gamma'_i + 1)
    B'_i = ceil(B_i / m)
3. Compaction is admitted only if effective_alpha_i <= max_alpha_i.
4. Streams with lower priority (higher priority number) must be compacted before streams with higher priority.
