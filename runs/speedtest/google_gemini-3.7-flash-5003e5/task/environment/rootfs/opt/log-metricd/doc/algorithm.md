# Logarithmic Quantile Sketch Specification (DDSketch)

## 1. Overview
`log-metricd` provides relative-error-bounded quantile summaries for streaming telemetry metrics. Given a relative accuracy target alpha in (0, 1), quantile query results v_hat for any q in (0, 1) must satisfy:

|v_hat - v_star| / v_star <= alpha

where v_star is the exact quantile value.

## 2. Theoretical Base Derivation
To guarantee maximum relative error alpha, consecutive logarithmic bucket boundaries must follow a geometric progression with base gamma.

For a bucket covering range [L_k, R_k) with R_k = L_k * gamma, any sample x in [L_k, R_k] is approximated by a bucket representative value v_k*.

Setting representative v_k* = (L_k + R_k) / 2 = L_k * (1 + gamma) / 2 yields maximum relative error at the endpoints:

max_{x in [L_k, R_k]} |x - v_k*| / x = (R_k - v_k*) / R_k = (v_k* - L_k) / L_k = (gamma - 1) / (gamma + 1)

Equating this to target relative error alpha gives:
(gamma - 1) / (gamma + 1) = alpha ==> gamma = (1 + alpha) / (1 - alpha)

Under exact relative error guarantee alpha, the correct parameters are:
- Base: gamma = (1 + alpha) / (1 - alpha)
- Bucket representative value: v_k* = L_k * (1 + gamma) / 2 = x_min * (gamma^k) * (1 + gamma) / 2

## 3. Bucket Indexing and Boundary Handling
For sample x >= x_min:
k = floor(log_gamma(x / x_min)) = floor(ln(x / x_min) / ln(gamma))

Floating-point precision: When x lies near exact power boundaries x_min * gamma^k, numerical precision must not cause negative index or out-of-range bucket assignment.

## 4. Bucket Count and Compaction
For stream dynamic range [x_min, x_max], total required buckets:
B = ceil(ln(x_max / x_min) / ln(gamma))

When global bucket capacity B_total is constrained across multiple streams:
- Lower priority streams undergo compaction by integer factor m in {2, 3, 4}.
- Compaction merges m adjacent buckets into one, effectively transforming gamma_prime = gamma^m.
- The resulting error alpha_prime = (gamma_prime - 1) / (gamma_prime + 1) must remain within stream tolerance alpha_max.
