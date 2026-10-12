# Developer shortcuts. Secrets come from .env (see .env.example).

UV_RUN := uv run --quiet --env-file .env

.DEFAULT_GOAL := help

TB_REFERENCE_DIR := data/tb-reference

.PHONY: help usage usage-json tb-reference

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

usage: ## Show OpenRouter spend, limit and remaining credit for the key in .env
	@$(UV_RUN) python scripts/openrouter_usage.py

usage-json: ## Same as usage, as raw JSON (for scripts and the budget guard)
	@$(UV_RUN) python scripts/openrouter_usage.py --json

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
