# Developer shortcuts. Secrets come from .env (see .env.example).

UV_RUN := uv run --quiet --env-file .env

.DEFAULT_GOAL := help

TB_REFERENCE_DIR := data/tb-reference

.PHONY: help usage usage-json tb-reference test lint dry-run batch status watch

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

usage: ## Show OpenRouter spend, limit and remaining credit for the key in .env
	@$(UV_RUN) python -m scripts.openrouter_usage

usage-json: ## Same as usage, as raw JSON (for scripts and the budget guard)
	@$(UV_RUN) python -m scripts.openrouter_usage --json

# Published Terminal-Bench sets used as the novelty reference. terminal-bench@latest
# is the current release (66 tasks; 4.0 as of 2026-10). Only instruction.md and
# task.toml are kept per task; that's all the novelty check reads.
TB_REFERENCE_SETS := terminal-bench/terminal-bench terminal-bench/terminal-bench-2-1 \
	terminal-bench-pro/terminal-bench-pro terminal-bench-science/terminal-bench-science

tb-reference: ## Download published Terminal-Bench tasks (latest, 2.1, Pro, Science) for the novelty check
	@rm -rf $(TB_REFERENCE_DIR).tmp && mkdir -p $(TB_REFERENCE_DIR).tmp
	@for set in $(TB_REFERENCE_SETS); do \
		uv run --quiet harbor download $$set -o $(TB_REFERENCE_DIR).tmp/raw | grep -E "Successfully|rror"; \
	done
	@cd $(TB_REFERENCE_DIR).tmp/raw && find . -mindepth 3 -maxdepth 3 \( -name instruction.md -o -name task.toml \) \
		-exec sh -c 'mkdir -p ../slim/$$(dirname "$$1") && cp "$$1" ../slim/"$$1"' _ {} \;
	@rm -rf $(TB_REFERENCE_DIR) && mv $(TB_REFERENCE_DIR).tmp/slim $(TB_REFERENCE_DIR) && rm -rf $(TB_REFERENCE_DIR).tmp
	@for d in $(TB_REFERENCE_DIR)/*/; do echo "  $$(ls $$d | wc -l | tr -d ' ') tasks  $$d"; done

N ?= 3
SEED ?= 1
BUDGET ?= 20

status: ## One-screen view of background work: processes, containers, authoring turns, ledger, spend
	@uv run --quiet python -m scripts.status

watch: ## Live status, interactive TUI: candidates, per-stage timeline, files, jobs (q to quit); EVERY=5 sets refresh seconds (default 30)
	@uv run --quiet python -m scripts.status --watch $(or $(EVERY),30)

plan: ## Show docs/plan.md checklist progress per phase (ARGS=--remaining lists open items)
	@bash scripts/track-plan.sh $(ARGS)

test: ## Run unit tests
	@uv run --quiet pytest -q

lint: ## Lint pipeline code (AfterQuery's validator/validate.py excluded)
	@uv run --quiet ruff check . --exclude validator/validate.py
	@bash scripts/check_repo_hygiene.sh

calibrate: ## Calibrate every gated candidate in one wave (wider than per-batch; uses OPUS_CONCURRENCY)
	@$(UV_RUN) python -m scripts.calibrate_candidates

dry-run: ## Run the batch pipeline with fixtures instead of model calls (free; real gates)
	@uv run --quiet python -m scripts.run_batch --n 1 --dry-run

batch: ## Generate and gate N candidates (N=3 SEED=1 BUDGET=20); DEV_MODE=1 for cheap plumbing runs
	@$(UV_RUN) python -m scripts.run_batch --n $(N) --seed $(SEED) --budget $(BUDGET)
