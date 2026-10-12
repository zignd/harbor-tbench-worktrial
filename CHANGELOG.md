# Changelog

What we did, why, and the design tradeoffs. Newest first. Each entry is stamped `### HH:MM ±HH:MM · Title` under its `## YYYY-MM-DD` day: local time with its UTC offset, taken from when the change was committed. Spend figures come from `make usage` (OpenRouter `/api/v1/key`).

## 2026-10-12

### 16:12 -03:00 · Novelty gate against every published Terminal-Bench set; `harbor check` evaluated
- **Novelty corpus:** `make tb-reference` downloads every Terminal-Bench set on the Harbor hub into git-ignored `data/tb-reference/` (~2 min), keeping only `instruction.md` + `task.toml` (3.6 MB). That's 425 tasks:
  - `terminal-bench@latest`, 66 tasks. This matches Terminal-Bench **4.0** (Aug 2026), and none of its tasks overlap with 2.x.
  - 2.1, 89 tasks.
  - Pro, 200 tasks.
  - Science, 70 tasks.
- **Why all of them, and not just the latest:** the README forbids reusing or adapting *any* public task, so newer releases don't replace older ones as things to avoid.
- **Plan change (delta 11):** novelty moved from a Phase 3 report to an **early gate**. It has three layers:
  1. The TB concept list goes in the blueprint prompt ("don't build these or variants").
  2. At blueprint review: 13-gram + TF-IDF, then a Sonnet "same underlying task?" judge on the top-3 nearest TB tasks.
  3. The same check on the finished package before calibration.
- **Tradeoff:** text overlap alone only catches copied wording. The semantic judge catches the same task reworded, at about one small Sonnet call per candidate. Thresholds will be calibrated on TB-vs-TB similarity so tasks that merely share a domain aren't rejected.
- **`harbor check` evaluated:** it runs a reviewer agent in a Harbor job. It works with terminus-2 + Sonnet 4.6 through our gateway, at $0.084 for `fix-git`. Its default rubric has **11 criteria**, not the 19 we assumed. AfterQuery's own `fix-git` fails 4/11, including two instruction↔test alignment criteria (the tests check files the instruction never names).
  - **Decision:** wrap `harbor check` with a custom rubric as the alignment/quality gate, instead of building a judge.
- **Spend:** `harbor check` $0.084, plus the meta-task spikes (accounted when they finish).

### 15:54 -03:00 · Correction: OpenRouter usage counters lag
- My earlier claim that "Harbor's `cost_usd` overstates spend by ~50%" was wrong. The $0.0775 reading was taken 5 s after the Opus trial, before OpenRouter had counted all of it. The settled total ($0.1176) matches Harbor's estimate of $0.1173.
- OpenRouter's `/api/v1/key` `usage` and `limit_remaining` also update out of sync. At one point they implied $0.118 vs $0.145 spent.
- **Changes:**
  - The ledger records Harbor's per-trial `cost_usd`, which is immediate and attributable to a task.
  - Reconcile against OpenRouter only after the counters settle (~1-2 min).
  - The budget guard uses the larger of `usage` and `limit − remaining`.
  - `make usage` now prints both, as `used` and `spent*`.
- Fixed the earlier entry, `docs/harbor-notes.md` and the plan's credentials note.

### 15:51 -03:00 · Phase 0: Harbor baseline, first Opus trial, meta-task template
- **Examples:** oracle 6/6 = 1.0 and nop 6/6 = 0.0, no exceptions. Trials took 9-108 s, the verify step 4-26 s, and no `uvx` install failures across 12 runs. Docker image caching works (env setup ~1 s once built). Details are in `docs/harbor-notes.md`.
- **First Opus 4.8 trial** (`fix-git`, `max_turns=200`): reward 1.0 in 11 turns and 68 s, costing **about $0.117**, with 85% of input tokens served from the prompt cache.
  - *Corrected later the same day:* this entry first said "$0.0775 actual, Harbor overstates by ~50%". That reading was taken 5 s after the run, before OpenRouter had counted it. The settled figure matches Harbor's `cost_usd` ($0.1173). See the 15:54 entry.
  - fix-git is "Easy". Generated Medium/Hard tasks will run longer, so per-trial cost still has to be measured on our own tasks.
- **Confirmed mechanics:**
  - `--ak max_turns=200` reaches terminus-2 (it's in the trial config, and terminus-2 logs a warning).
  - `-k`/`-n` work.
  - The trajectory JSON holds per-step reasoning, keystrokes and observations, which is what the judges and the command scan need.
- **Meta-task template** (`generator/metatask/`) and renderer (`generator/author.py`):
  - The instruction is adapted from Meta-Task's template, with our rules.
  - The synthesis image uses the same base (`python:3.13-slim-bookworm`) that generated tasks must use, so the author can reproduce the task env without Docker.
  - The in-container `check_package.py` gives the meta-task a "package complete" reward.
  - `artifacts = ["/app/output"]` collects the package.
- **Fixtures:** sanitized oracle, nop and Opus job dirs in `tests/fixtures/harbor_jobs/` for unit tests (no secrets; absolute paths replaced by `<REPO>`).
- **Spend:** Opus trial ~$0.117. Running total ~$0.118.

### 15:30 -03:00 · Dev mode: cheap model for plumbing iterations
- `DEV_MODE=1` routes every model call (authoring, judges, red-team, and the terminus-2 eval agent) to `DEV_MODEL`, default `deepseek/deepseek-v4.1-flash`. That's $0.15/$0.60 per M tokens vs Sonnet's $3/$15 and Opus's $5/$25, so ~20-40× cheaper. It's validated through both the OpenAI client and LiteLLM.
- **Why:** the README rule is "Generate tasks with `claude-sonnet-4.6` and benchmark difficulty only against `claude-opus-4.8`. Use no other models for either." It restricts *generating* and *benchmarking*, and says nothing about debugging the pipeline. Most early runs only test plumbing (runner parsing, meta-task wiring, calibration loop, ledger), where paying Opus prices buys nothing.
- **Guardrails:**
  - Dev output goes to `output-dev/` (git-ignored).
  - `RUN_MODE` tags ledger entries `dev` vs `official`.
  - `config.assert_official_models()` makes ship/report steps refuse to run with non-official models.
  - `OFFICIAL_MODEL` / `OFFICIAL_EVAL_MODEL` are now constants, separate from the env overrides.
- **Tradeoff:** DeepSeek behaves differently from Opus (and small models are brittle with terminus-2's keystroke interface, per Tmax). So dev runs never inform difficulty, tuning or any reported metric. They only prove the code works. Dev spend will be reported separately here.
- Checklist: added dev-mode steps before the official meta-task spike, the pilot batch and the first calibration (10/75 items done).
- **Spend:** ~$0.00002 (two DeepSeek validation calls; still $0.0003 total).

### 15:19 -03:00 · Plan as a work checklist
- Replaced the prose "Phases" section of `docs/plan.md` with a **work checklist**: 71 concrete items across Phases 0-4, each naming its output and how we know it's done, with a progress counter (9/71 done).
- Items that call a model are marked 💲, so spend is visible before work starts. Go/no-go checkpoints are explicit: the meta-task spike, and cost per learnable task after the pilot.
- Removed per-phase day estimates. Progress is tracked by ticked items, not by the calendar.

### 15:12 -03:00 · Agent guidance (`AGENTS.md`, `CLAUDE.md`)
- Added `AGENTS.md` with the work-trial constraints, budget rules, commands, changelog and commit conventions. `CLAUDE.md` imports it, so Claude Code and other agents follow one source of truth.
- **Why:** most of the work is done with AI assistance. Writing the hard constraints (allowed models, the 3600 s timeout, valid-failure rule, novelty, $75 reserve) where every agent reads them stops them from being broken by accident.

### 15:07 -03:00 · Spend tracking (`make usage`) and spend discipline
- `make usage` / `make usage-json` (`scripts/openrouter_usage.py`) report limit, spend, remaining credit and key expiry from OpenRouter's per-key endpoint. The account-level `/credits` endpoint needs a management key, which we don't have.
- `docs/plan.md` gained a "Spend discipline" section:
  - Opus runs only after every cheap gate passes.
  - Exact curtailment of the 5-run test.
  - Stop calibrating a task on its first invalid failure.
  - A protected $75 reserve.
  - Batches scaled 1 → 3 → 10 → 15, gated on cost per learnable task.
- **Tradeoff:** curtailment reports some tasks as `k/n` with n < 5. The verdict is mathematically identical to running all 5 runs (after 1 pass and 2 fails, at most 3 of 5 can pass). Shipped tasks can be topped up to a full 5 runs if budget remains.

### 14:59 -03:00 · Inference credentials
- The issued key is an **OpenRouter** key ($500 limit, expires 2026-10-23). `https://api.aqinference.com/v1` (the README's gateway) returns 401 for it, so `generator/config.py` now defaults `OPENROUTER_API_BASE` to `https://openrouter.ai/api/v1`.
- Validated both allowed models with one tiny call each:
  - Sonnet 4.6 through the OpenAI client (generator path).
  - Opus 4.8 through LiteLLM (Harbor path).
- Secrets live in a git-ignored `.env` (mode 600). `.env.example` documents the variables.
- **Spend:** $0.0003 (validation calls).

### 14:54 -03:00 · Plan and research (`docs/plan.md`, `docs/research/`)
- Wrote the pipeline plan covering Parts 1-3 and stretch goals A-D.
- Read eight papers in full and kept text versions in `docs/research/` (PDFs are git-ignored but re-downloadable from arXiv). They cover task quality, reward hacking, terminal task synthesis, and learnability.
- Decisions they drove:
  - Author tasks as a **Harbor meta-task**: Sonnet runs as terminus-2 inside a container, and the finished task is collected via `artifacts` (Meta-Task).
  - A **blueprint + rubric review** before building (CLI-Universe, SkillSynth).
  - Difficulty levers aimed at Opus's documented failure modes, weak self-verification and partial implementation (CLI-Universe, Meta-Task, SkillSynth).
  - Verifier thresholds as a continuous tuning knob (Tmax).
  - An oracle **3/3 determinism gate**, because environment randomness would look learnable without being so (Foster & Foerster).
  - Pass audits and a Sonnet red-team against reward hacking (Terminal Wrench, HVTB).
- **Tradeoff:** a meta-task reuses Harbor's agent, logs and cost tracking, but the authoring container can't run Docker. Real build/oracle/nop checks therefore happen in host-side gates and feed back through repair rounds. A custom `docker exec` authoring loop is the fallback if the Phase 0 spike fails.

### 14:30 -03:00 · Development environment
- Made the repo a **uv** project: `pyproject.toml` + `uv.lock` pin `harbor==0.24.0`, `openai`, `pydantic` and `toml`, with Python 3.13 via `.python-version`.
- **Why:** with Harbor in the project venv, `validator/validate.py`'s native Harbor schema cross-check actually runs. Previously it was silently skipped when Harbor wasn't importable. It also pins one Harbor version for both the CLI and our code.
- `scripts/*.sh` run through `uv run`.
- Fixed a template bug: `validate.sh` broke on relative task paths after `cd validator`.
- All 6 examples pass the validator, including the Harbor cross-check.
