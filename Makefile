# =============================================================================
# Makefile — IncuBrix B-roll Video Engine
# =============================================================================
.PHONY: up down logs test test-unit migrate batch corpus build build-cpu clean help

COMPOSE = $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)

## Start all services in the background
up:
	$(COMPOSE) up -d

## Stop all services (keep volumes)
down:
	$(COMPOSE) down

## Tail logs for all services
logs:
	$(COMPOSE) logs -f

## Build / rebuild Docker images
build:
	$(COMPOSE) build --no-cache

## Build CPU-only images (explicitly disables GPU/cuda assumptions)
build-cpu:
	DOCKER_BUILDKIT=1 $(COMPOSE) build --no-cache

## Run alembic migrations
migrate:
	$(COMPOSE) run --rm api alembic upgrade head

## Run pytest test suite
test:
	$(COMPOSE) run --rm api pytest tests/ -v --no-header -q

## Run unit tests directly in the host environment
test-unit:
	python -m pytest -q tests/unit

## Run the batch runner
batch:
	$(COMPOSE) run --rm api python batch/batch_runner.py

## Run the creator test corpus in mock mode
corpus:
	MOCK_MODE=true $(COMPOSE) run --rm api python batch/batch_runner.py --input tests/fixtures/creator_scripts --output batch_results/creator_corpus

## Remove containers AND volumes (destructive!)
clean:
	$(COMPOSE) down -v --remove-orphans

## Show available targets
help:
	@grep -E '^##' Makefile | sed 's/^## //'
