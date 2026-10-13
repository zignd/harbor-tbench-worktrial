# Logarithmic quantile sketch

The service keeps a histogram for each registered latency stream. A stream is
configured with a positive lower bound `x_min`, an upper bound `x_max`, and a
target relative error `alpha` with `0 < alpha < 1`.

For numerical safety the implementation reserves a small epsilon:

    alpha_e = alpha * (1 - 2**-40)
    gamma = (1 + alpha_e) / (1 - alpha_e)

Bucket `k` covers `[x_min * gamma**k, x_min * gamma**(k+1))`. The last bucket
is truncated at `x_max`. A bucket representative is

    R_k = x_min * gamma**k * (1 + alpha_e)

For every `x` in that interval, `|R_k - x| / x <= alpha_e < alpha`. Thus a
nearest-rank quantile reconstructed from representatives retains the configured
relative error. Values below `x_min` are clamped to the first bucket; values
above `x_max` are counted as overflow and cannot make an in-range quantile NaN.
Exact powers of gamma may move to either adjacent bucket because of floating
point rounding. Both neighboring representatives are within the same error
bound, so index calculations clamp rather than rejecting or panicking.

The planner may collapse `m` adjacent native bins, with `m` in `{1,2,3,4}`, only
when the resulting interval ratio is strictly below the gamma corresponding to
the stream's maximum allowed error. Collapsed buckets use the same
representative rule. Higher-priority streams are given finer representations
first, but the sum of allocated bucket counts never exceeds the global budget.

Quantile queries use the nearest-rank convention: for `n` observations and
quantile `q`, the rank is `ceil(q*n)`, and the representative for the bucket
containing that order statistic is returned. Empty sketches return zero rather
than NaN.
