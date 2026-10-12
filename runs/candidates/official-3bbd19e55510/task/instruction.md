The metrics pipeline at /app has been flagged for two issues.

Pasted output from the nightly validation job:

  WARN  channel=temp      ema_final=47.231  expected_range=[52.1, 53.9]  FAIL
  WARN  channel=temp      ema_final=47.231  expected_range=[52.1, 53.9]  FAIL
  INFO  channel=pressure  ema_final=1.013   expected_range=[0.98, 1.02]  PASS
  PERF  throughput=31,204 sps  required=50000  FAIL

Your goal:

1. The EMA engine must produce numerically correct results. For every channel, the final EMA value written to /app/output/metrics_summary.json must agree with the correct closed-form EMA recurrence to within an absolute error of 1e-4. The recurrence is: EMA_n = alpha * x_n + (1 - alpha) * EMA_{n-1}, where alpha = 2 / (window + 1) and EMA_0 = x_0 (the first sample, not zero).

2. The pipeline must sustain at least 50,000 samples per second as measured by the benchmark script at /app/bench/run_bench.sh, which writes its result to /app/bench/throughput.txt as a single integer (samples per second).

3. The file /app/output/metrics_summary.json must exist after running /app/run_pipeline.sh and must contain a JSON object mapping each channel name to its final EMA value (a float) and the sample count (an integer), e.g.: {"temp": {"ema": 52.87, "count": 10000}, ...}.

Investigate the codebase and logs to find and fix the root causes. Do not change the public interface of run_pipeline.sh or the JSON output schema.
