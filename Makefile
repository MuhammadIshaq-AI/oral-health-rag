# DentalCare AU — developer entry points. On Windows run from Git Bash or WSL.
UV ?= uv
PY := $(UV) run python
# Experiment config: defaults to EXPERIMENT_CONFIG from .env (configs/default.yaml if unset).
CONFIG ?=
CONFIG_ARG := $(if $(CONFIG),--config $(CONFIG),)

.PHONY: help install dev dev-api dev-frontend qdrant ingest ingest-refresh stats eval eval-quick \
        test lint format export purge up down audio

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install Python (all extras) and frontend dependencies
	$(UV) sync --python 3.11 --extra ml --extra ingest --extra stt --extra tts --extra anthropic
	cd frontend && npm ci

qdrant: ## Start the Qdrant vector database (Docker)
	docker compose up -d qdrant

dev: qdrant ## Run Qdrant, the API (reload) and the Vite dev server
	$(MAKE) -j2 dev-api dev-frontend

dev-api: ## Run only the API on :8000
	$(if $(CONFIG),EXPERIMENT_CONFIG=$(CONFIG) ,)$(UV) run uvicorn app.main:app --app-dir api --reload --port 8000

dev-frontend: ## Run only the frontend on :5173
	cd frontend && npm run dev

ingest: qdrant ## Fetch (cached), chunk, embed and index the corpus
	$(PY) -m ingest.cli run

ingest-refresh: qdrant ## Re-download every page, then re-index
	$(PY) -m ingest.cli run --refresh

stats: ## Corpus statistics
	$(PY) -m ingest.cli stats

eval: ## Full evaluation suite → reports/eval-<timestamp>.md
	$(PY) -m eval.run $(CONFIG_ARG)

eval-quick: ## Retrieval + triage only (no LLM calls)
	$(PY) -m eval.run $(CONFIG_ARG) --only retrieval,triage

audio: ## Synthesise the TTS-proxy speech test set
	$(PY) -m eval.audio.synth

test: ## Unit tests (no models / network)
	$(UV) run pytest -m "not models and not slow"

lint: ## Ruff lint + format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Auto-format
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

export: ## Export research logs to CSV
	$(PY) -m app.telemetry.cli export

purge: ## Delete ALL logged research data (asks for confirmation)
	$(PY) -m app.telemetry.cli purge

up: ## Full stack in Docker (api + frontend + qdrant)
	docker compose --profile full up -d --build

down: ## Stop all containers
	docker compose --profile full --profile local-llm down
