# Harbor 0.24.0: how it actually behaves (Phase 0 findings)

Measured on this machine (Docker 29.8, 10 CPUs, 14.6 GB) on 2026-10-12. The pipeline code (`evaluator/harbor_runner.py`) is written against these facts.

## Running jobs

```bash
uv run --env-file .env harbor run -p <task-or-dataset-dir> -a <agent> [-m <model>] \
    [--ak max_turns=200] [-k <attempts>] [-n <concurrent>] -o jobs --job-name <name> -y
```

- `-p` takes one task dir or a dir of tasks (e.g. `-p examples` runs all 6).
- `-y` skips confirmation prompts, which non-interactive runs need.
- `--ak key=value` reaches the agent: `max_turns=200` shows up in the trial `config.json` under `agent.kwargs`. terminus-2 logs a warning that the limit is "artificially limited".
- Harbor also accepts `--env-file` and `--artifact <container path>` directly.

## Job directory layout

```
jobs/<job-name>/
  config.json  result.json  job.log  lock.json
  <task>__<id>/                 # one per trial
    config.json  result.json  trial.log  lock.json
    agent/        oracle.txt (oracle) | trajectory.json, terminus_2.pane, recording.cast (terminus-2)
    verifier/     reward.txt, ctrf.json, test-stdout.txt
    artifacts/    manifest.json + collected paths, mirrored by absolute path
                  (e.g. /logs/artifacts -> artifacts/logs/artifacts)
```

## Trial `result.json` (fields we use)

| Field | Meaning |
|---|---|
| `verifier_result.rewards.reward` | Reward as a float (1.0 / 0.0) |
| `exception_info` | `null` on success, otherwise the infra/agent exception (retry or exclude) |
| `agent_result.n_input_tokens`, `n_cache_tokens`, `n_output_tokens` | Token counts (`null` for oracle/nop) |
| `agent_result.cost_usd`, `model_usage{model: {...}}` | **Harbor's estimate**, which overstates actual spend (see below) |
| `agent_result.metadata.n_episodes`, `summarization_count`, `api_request_times_msec` | terminus-2 turns, context summarizations, per-call latency |
| `environment_setup` / `agent_execution` / `verifier` `.started_at` / `.finished_at` | Per-stage timing |
| `task_checksum` | Content hash of the task; useful as a cache key |

The job-level `result.json` has `stats.evals.<agent>__<source>.reward_stats` (trial names per reward) and `exception_stats`.

## Trajectory (`agent/trajectory.json`, terminus-2)

`{schema_version, session_id, agent, steps[], final_metrics}`. Each step has:
- `message`: the model's "Analysis: … Plan: …" reasoning text.
- `tool_calls[]`: `bash_command` with `keystrokes` and `duration`.
- `observation.results[].content`: terminal output.
- `metrics`: prompt/completion tokens and cost.

This is what the pass-audit and failure judges read. The command scan works off `tool_calls[].arguments.keystrokes`.

## Measured baseline

**Examples, oracle and nop (no API cost):** oracle 6/6 = 1.0 and nop 6/6 = 0.0, with no exceptions. Each trial took 9-108 s. The verify step (verify-time `uvx` pytest install) took 4-26 s, with no install failures across 12 runs. Environment setup took 3-24 s cold and ~1 s cached, so image caching works across jobs.

**First Opus 4.8 trial** (`fix-git`, terminus-2, `max_turns=200`):
- Reward 1.0 in 11 turns, 1 m 8 s wall time, no summarization.
- Tokens: 45,180 input (**38,595 cached = 85%**), 2,276 output.
- **Cost: about $0.117**, which matches Harbor's `cost_usd` ($0.1173). A `make usage` read 5 s after the run showed only $0.0775 because OpenRouter hadn't counted it yet. A later read settled at $0.1176 total.
- **OpenRouter's `/api/v1/key` counters lag** by seconds to minutes, and `usage` and `limit_remaining` don't update together. At one point they implied $0.118 vs $0.145 spent.
- **So the ledger records Harbor's per-trial `cost_usd`**, which is available immediately and attributable to a task. Reconcile it against OpenRouter only after the counters settle (re-read after ~1-2 min). `make usage` shows both `used` and `limit − remaining`, and the budget guard uses the larger of the two.
- fix-git is an "Easy" task. Medium/Hard tasks should run many more turns (TB-style tasks average ~20-40), so expect roughly $0.3-1.5 per Opus trial. That's to be confirmed on generated tasks.
