# Developer shortcuts. Secrets come from .env (see .env.example).

UV_RUN := uv run --quiet --env-file .env

.DEFAULT_GOAL := help

.PHONY: help usage usage-json

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

usage: ## Show OpenRouter spend, limit and remaining credit for the key in .env
	@$(UV_RUN) python scripts/openrouter_usage.py

usage-json: ## Same as usage, as raw JSON (for scripts and the budget guard)
	@$(UV_RUN) python scripts/openrouter_usage.py --json
