# =============================================================================
# Makefile — IncuBrix B-roll Video Engine
# =============================================================================
.PHONY: up down logs test migrate batch build clean help

COMPOSE = docker compose

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

## Run alembic migrations
migrate:
	$(COMPOSE) run --rm api alembic upgrade head

## Run pytest test suite
test:
	$(COMPOSE) run --rm api pytest tests/ -v --no-header -q

## Run the batch runner
batch:
	$(COMPOSE) run --rm api python batch/batch_runner.py

## Remove containers AND volumes (destructive!)
clean:
	$(COMPOSE) down -v --remove-orphans

## Show available targets
help:
	@grep -E '^##' Makefile | sed 's/^## //'
