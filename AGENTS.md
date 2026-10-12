# AGENTS.md

Guidance for AI agents (and humans) working in this repo. This is an AfterQuery work trial: a pipeline that generates Terminal-Bench / Harbor tasks and keeps only the *learnable* ones. **`README.md` is the spec, and `docs/plan.md` is the plan we follow.** Read both before starting non-trivial work.

## Work-trial constraints (never violate)

- **Models:** anything that **generates a task, measures its difficulty, or decides whether it ships** uses only `anthropic/claude-sonnet-4.6` (authoring, plus judges and red-team) and `terminus-2` + `openrouter/anthropic/claude-opus-4.8` (calibration). No cheap proxies for difficulty, and no embedding models in that path.
- **Dev mode is the one exception:** `DEV_MODE=1` routes every call to `DEV_MODEL` (default `deepseek/deepseek-v4.1-flash`, ~20-40× cheaper) for **plumbing iterations only**. Dev results go to `output-dev/`, are tagged `dev` in the ledger, and are **never** shipped, calibrated on, or counted in metrics. Shipping and reporting code must call `config.assert_official_models()`. The README rule ("use no other models for either") covers generating and benchmarking; dev runs do neither. Report dev spend separately in `CHANGELOG.md`.
- **Learnable band:** exactly 1-3 of 5 Opus runs pass all tests. Don't change Opus's agent, sampling or thinking settings, because that changes what "learnable" means.
- **Agent timeout:** `[agent].timeout_sec = 3600.0` in every task. Timeouts and running out of turns (`max_turns` ≤ 200) are **never** valid failures.
- **Valid failures only:** a shipped task fails because the model couldn't solve it. It must not fail because of an ambiguous spec, an over-strict test, a broken or flaky env, or a tmux/pager quirk. For every shipped task we must be able to say *why* the model fails it.
- **Novelty:** don't reuse or adapt public tasks (including `examples/`). Don't clone public repos for the agent to patch. The generator writes every problem, environment and solution itself.
- **Task format:** exactly as `README.md` describes. `tests/test.sh` writes `1`/`0` to `/logs/verifier/reward.txt`. The canary goes in `solve.sh`, the `Dockerfile` and `test_outputs.py`, never in `instruction.md`.
- **Reward hacking:** nothing answer-bearing in `environment/`. Tests check outcomes on hidden inputs, not source strings or installed packages.

## Budget (one $500 OpenRouter key, expires 2026-10-23 07:00 UTC)

- Run **`make usage`** before and after any step that calls a model, and report the delta. `make usage-json` gives the machine-readable version.
- Follow "Spend discipline" in `docs/plan.md`:
  - No Opus trial until every cheap gate passes.
  - Stop calibrating a task early with exact curtailment, and also on its first invalid failure or hacked pass.
  - Never let remaining credit drop below the **$75 reserve**.
  - Scale batches in steps.
- **Ask the user before** any action expected to cost more than ~$10, or any batch of Opus trials.
- For development, prefer the cheapest option that exercises the code: recorded fixtures and `--dry-run` (free), then `DEV_MODE=1` (cents), then official models (dollars), used only once the plumbing works.

## Environment and commands

- Python 3.13 via **uv** (Homebrew). Run `uv sync` once. Always run code with `uv run`, never system `python`/`pip`.
- Secrets live in **`.env`** (git-ignored, see `.env.example`). Load them with `uv run --env-file .env <cmd>`. Never print, log or commit the key.
- Harbor 0.24.0 is a project dependency: `uv run --env-file .env harbor run -p <task> -a oracle|nop|terminus-2 ...`.
- Validate a task: `bash scripts/validate.sh <task_dir>`.
- Tests and lint: `uv run pytest`, `uv run ruff check .`.
- `harbor/` is vendored Harbor source, **read-only**. The real package is in `.venv`.
- Docker runs locally (10 CPUs, 14.6 GB). Keep Opus concurrency ≤3.

## Plan checklist

`docs/plan.md` → "Work checklist" tracks progress. When an item is finished, tick it (`- [x]`, with the commit hash if useful) and update the **Progress** counter **in the same commit**. If the work reveals a missing item, add it. Don't silently skip or drop items; mark them `~~struck~~` with the reason instead.

## Changelog (required)

`CHANGELOG.md` is a graded deliverable. AfterQuery reads it to understand what we did, **why**, and the **tradeoffs**.
- **Update it in the same commit as the change.** Every commit that changes behavior, the pipeline design, results or spend adds an entry. Pure typo fixes are the only exception.
- Entries go under a dated heading (`## YYYY-MM-DD`), newest first. Each entry has a **timestamped** heading, `### HH:MM ±HH:MM · Title` (local time with UTC offset, e.g. `### 15:12 -03:00 · Agent guidance`; get it with `date "+%H:%M %z"`). Each entry says what changed, why, and any tradeoff or rejected alternative.
- Record **measured numbers honestly**: spend per phase (from `make usage`), funnel counts, pass distributions, failures, and things that didn't work.

## Git

- **Conventional Commits** for titles (`feat:`, `fix:`, `docs:`, `build:`, `test:`, `refactor:`, `chore:`), with a bullet-point body explaining what and why. AfterQuery reads the history, so keep commits small and meaningful.
- Branch `main`, remote `origin` (private `zignd/harbor-tbench-worktrial`). Push after committing unless told otherwise. Never force-push without asking.
- Never commit `.env`, research PDFs (`docs/research/*.pdf`), `jobs/` or `trials/` run outputs.

## Code conventions

- Follow the layout in `docs/plan.md`: `generator/`, `validator/`, `evaluator/`, `analysis/`, `scripts/`, `tests/`, `output/` (shipped tasks only).
- Write stages as small pure functions over a task dir, with results logged to the ledger. Keep decision logic (band verdicts, budget guard, lints) unit-tested.
- Match the existing style: type hints, short docstrings, standard library first, new dependencies via `uv add`.

## Reference material

- `docs/plan.md`: architecture, phases, budget and spend rules.
- `docs/research/`: the eight papers behind the design (text versions plus `README.md` with arXiv links).
- `examples/`: Harbor task *format* reference only (all six are "Easy", below our target band).
