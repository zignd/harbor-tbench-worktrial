# Changelog

What we did, why, and the design tradeoffs. Newest first. Each entry is stamped `### HH:MM ±HH:MM · Title` under its `## YYYY-MM-DD` day: local time with its UTC offset, taken from when the change was committed. Spend figures come from `make usage` (OpenRouter `/api/v1/key`).

## 2026-10-12

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
