# Model speed test: authoring through the free gates

*Exploratory. Each model authored the same accepted blueprints with the real authoring meta-task (terminus-2, 60-turn cap, 20-minute wall clock for the first round, one repair round if time remained), then the package went through structure, lint, leak scan, oracle 3/3 and nop. Runs were parallel on one machine, so times include contention (equal for every model). Data: `runs/speedtest/results.json`.*

| Model | Valid packages | Median time to valid | Mean turns (1st round) | Mean $ per blueprint |
|---|---|---|---|---|
| `openai/gpt-5.6-luna` | 2/3 | 19.6 min | 9 | $0.03 |
| `google/gemini-3.8-flash` | 0/3 | n/a | 49 | $1.06 |
| `google/gemini-3.7-flash` | 0/3 | n/a | 41 | $0.66 |
| `xiaomi/mimo-v2.6-pro` | 0/3 | n/a | 2 | $0.02 |
| `z-ai/glm-5.3-flash` | 0/3 | n/a | 9 | $0.02 |

## Per run

| Model | Blueprint | Attempts | Valid after | Cost | First problems |
|---|---|---|---|---|---|
| `openai/gpt-5.6-luna` | telemetry-session-attribution-serv | 1 | 11.1 min | $0.02 |  |
| `openai/gpt-5.6-luna` | ddsketch-telemetry-aggregator-repa | 2 | never | $0.05 | oracle passed 0/3 (must be deterministic): ____________ test_quantile_ |
| `openai/gpt-5.6-luna` | quant-risk-batch-reconciler-deploy | 1 | 19.6 min | $0.02 |  |
| `google/gemini-3.8-flash` | ddsketch-telemetry-aggregator-repa | 2 | never | $1.14 | structure: environment/ has no Dockerfile or docker-compose.yaml and t |
| `google/gemini-3.7-flash` | telemetry-session-attribution-serv | 2 | never | $0.75 | leak: token found in image file /opt/telemetry-service/docs/spec.md |
| `google/gemini-3.7-flash` | quant-risk-batch-reconciler-deploy | 2 | never | $0.21 | structure: Missing required file: instruction.md |
| `google/gemini-3.8-flash` | quant-risk-batch-reconciler-deploy | 2 | never | $1.05 | structure: Missing required file: instruction.md |
| `google/gemini-3.8-flash` | telemetry-session-attribution-serv | 2 | never | $1.00 | leak: token found in image file /opt/telemetry-service/docs/spec.md |
| `xiaomi/mimo-v2.6-pro` | telemetry-session-attribution-serv | 2 | never | $0.02 | structure: Missing required file: instruction.md |
| `z-ai/glm-5.3-flash` | quant-risk-batch-reconciler-deploy | 2 | never | $0.03 | structure: Missing required file: instruction.md |
| `xiaomi/mimo-v2.6-pro` | ddsketch-telemetry-aggregator-repa | 2 | never | $0.03 | structure: Missing required file: instruction.md |
| `xiaomi/mimo-v2.6-pro` | quant-risk-batch-reconciler-deploy | 2 | never | $0.00 | structure: Missing required file: instruction.md |
| `z-ai/glm-5.3-flash` | ddsketch-telemetry-aggregator-repa | 2 | never | $0.01 | structure: Missing required file: instruction.md |
| `z-ai/glm-5.3-flash` | telemetry-session-attribution-serv | 2 | never | $0.04 | lint: test_outputs.py is missing the canary GUID |
| `google/gemini-3.7-flash` | ddsketch-telemetry-aggregator-repa | 2 | never | $1.01 | lint: suggestive comment environment/rootfs/usr/bin/systemctl:5: # pyl |

## Findings

- **Only `openai/gpt-5.6-luna` produced valid packages inside the budget** (2 of 3, in 11 and 20 minutes, for $0.02 each, about 10 turns). The third failed its oracle (0/3) after a repair. It is also the cheapest per task by far.
- **The Gemini models were too slow for this budget, not necessarily unable.** Both `gemini-3.8-flash` and `gemini-3.7-flash` used 40-60 turns and $0.2-1.1 per blueprint, and none passed the gates within 20 minutes plus one 10-minute repair, with 15 jobs sharing one machine. In the earlier solo probe, `gemini-3.8-flash` needed about 40 minutes and three rounds for one blueprint. Their failures were ordinary pipeline findings (missing `instruction.md`, a leak flag, a lint hit), not signs of a broken model.
- **`mimo-v2.6-pro` and `glm-5.3-flash` made almost no progress** (1-13 agent steps in 20 minutes, cost under $0.05), most likely very slow reasoning steps or an incompatibility with the terminus-2 loop. Their packages were missing `instruction.md`.
- **Caveat on quality:** luna's packages are small (solutions of 14-54 lines, tests of 20-49 lines, 7-10 environment files, instructions of 3-7 lines). Passing the free gates says nothing about difficulty; the quality check, red-team and calibration decide that, and simple tasks may be too easy for a strong solver. A task authored and solved by the same model (luna) is the "professors helping professors" setup.
- **Limits of this test:** one run, 3 blueprints, a single machine under load, a 20-minute cap that favours fast models, and gates only (no calibration).

## Decision

Run the rest of the pipeline with **`openai/gpt-5.6-luna` in every role** (about 76% on Terminal-Bench 2.1 with the Codex harness, tool calls supported, $0.20/$1.20 per M tokens), with calibration right after the build gates (`CALIBRATE_FIRST=1`) and a 60-turn authoring cap. The gemini-3.8-flash candidates already generated stay on disk under their own model label and are excluded from the report.
