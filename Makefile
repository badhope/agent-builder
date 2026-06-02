# DocFormatConverter — developer command surface.
# `make` (no args) prints help.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# ---- Paths ----
BACKEND_DIR := backend
FRONTEND_DIR := frontend
MINIPROGRAM_DIR := miniprogram
DEPLOY_DIR  := deploy
SCRIPTS_DIR := $(BACKEND_DIR)/scripts
PYTHON      ?= python3
PIP         ?= $(PYTHON) -m pip
NODE        ?= node
PNPM        ?= $(shell command -v pnpm 2>/dev/null || echo npm)
NPM         ?= $(shell command -v npm 2>/dev/null || echo npm)

# ---- Python tooling ----
RUFF        := $(PYTHON) -m ruff
BLACK       := $(PYTHON) -m black
MYPY        := $(PYTHON) -m mypy
PYTEST      := $(PYTHON) -m pytest
BANDIT      := $(PYTHON) -m bandit
PIP_AUDIT   := $(PYTHON) -m pip_audit

# ---- Docker ----
COMPOSE_DEV  := docker compose -f docker-compose.dev.yml
COMPOSE_PROD := docker compose

# ============================================================================
# Help
# ============================================================================
.PHONY: help
help:  ## show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ============================================================================
# Setup
# ============================================================================
.PHONY: install
install:  ## install backend + frontend dependencies
	$(PIP) install -e ".[dev,worker]"
	cd $(FRONTEND_DIR) && $(PNPM) install
	@echo "✅ dependencies installed"

.PHONY: install-hooks
install-hooks:  ## install pre-commit hooks
	$(PYTHON) -m pre_commit install
	@echo "✅ pre-commit hooks installed"

.PHONY: env
env:  ## create .env from .env.example (idempotent)
	@test -f .env || cp .env.example .env
	@echo "✅ .env present"

.PHONY: keys
keys:  ## generate development JWT key pair in ./keys/
	@mkdir -p keys
	openssl genpkey -algorithm RSA -out keys/jwt_private.pem -pkeyopt rsa_keygen_bits:2048 2>/dev/null
	openssl rsa -in keys/jwt_private.pem -pubout -out keys/jwt_public.pem 2>/dev/null
	@echo "✅ JWT key pair generated under keys/"

# ============================================================================
# Development
# ============================================================================
.PHONY: dev-up
dev-up:  ## start development stack (api, worker, redis, postgres, minio, frontend)
	$(COMPOSE_DEV) up -d
	@echo "✅ dev stack up — API: http://localhost:8000  Frontend: http://localhost:5173  MinIO: http://localhost:9001"

.PHONY: dev-down
dev-down:  ## stop dev stack
	$(COMPOSE_DEV) down

.PHONY: dev-logs
dev-logs:  ## tail dev stack logs
	$(COMPOSE_DEV) logs -f --tail=200

.PHONY: dev-shell
dev-shell:  ## open shell in api container
	$(COMPOSE_DEV) exec api bash

.PHONY: dev-psql
dev-psql:  ## open psql shell
	$(COMPOSE_DEV) exec postgres psql -U docconverter docconverter

# ============================================================================
# Backend
# ============================================================================
.PHONY: api
api:  ## run API locally (uvicorn reload)
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: worker
worker:  ## run Celery worker locally
	cd $(BACKEND_DIR) && celery -A app.workers.celery_app worker -l info -c 2

.PHONY: beat
beat:  ## run Celery beat locally
	cd $(BACKEND_DIR) && celery -A app.workers.celery_app beat -l info

.PHONY: migrate
migrate:  ## apply database migrations
	cd $(BACKEND_DIR) && alembic upgrade head

.PHONY: revision
revision:  ## create a new alembic revision (usage: make revision m="add foo")
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed:  ## bootstrap admin user + default API key
	cd $(BACKEND_DIR) && $(PYTHON) scripts/bootstrap_admin.py

# ============================================================================
# Frontend
# ============================================================================
.PHONY: fe
fe:  ## run Vite dev server
	cd $(FRONTEND_DIR) && $(PNPM) dev

.PHONY: fe-build
fe-build:  ## production build
	cd $(FRONTEND_DIR) && $(PNPM) build

.PHONY: fe-lint
fe-lint:  ## lint frontend
	cd $(FRONTEND_DIR) && $(PNPM) lint

.PHONY: fe-test
fe-test:  ## run frontend tests
	cd $(FRONTEND_DIR) && $(PNPM) test

# ============================================================================
# Mini Program (WeChat / Taro)
# ============================================================================
.PHONY: mp-install
mp-install:  ## install mini-program dependencies
	cd $(MINIPROGRAM_DIR) && $(NPM) install

.PHONY: mp-dev
mp-dev:  ## start mini-program dev server (WeChat)
	cd $(MINIPROGRAM_DIR) && $(NPM) run dev:weapp

.PHONY: mp-dev-h5
mp-dev-h5:  ## start mini-program dev server (H5/web)
	cd $(MINIPROGRAM_DIR) && $(NPM) run dev:h5

.PHONY: mp-build
mp-build:  ## build mini-program for WeChat
	cd $(MINIPROGRAM_DIR) && $(NPM) run build:weapp

.PHONY: mp-build-h5
mp-build-h5:  ## build mini-program for H5/web
	cd $(MINIPROGRAM_DIR) && $(NPM) run build:h5

# ============================================================================
# Quality
# ============================================================================
.PHONY: format
format:  ## auto-format backend code
	$(RUFF) format $(BACKEND_DIR)
	$(BLACK) $(BACKEND_DIR)

.PHONY: lint
lint:  ## run linters
	$(RUFF) check $(BACKEND_DIR)
	$(BLACK) --check $(BACKEND_DIR)
	$(MYPY) $(BACKEND_DIR)

.PHONY: test
test:  ## run backend tests with coverage
	cd $(BACKEND_DIR) && $(PYTEST) --cov=app --cov-report=term-missing --cov-report=xml

.PHONY: test-fast
test-fast:  ## run fast tests only (skip slow/integration)
	cd $(BACKEND_DIR) && $(PYTEST) -m "not slow and not integration"

.PHONY: security-scan
security-scan:  ## bandit + pip-audit
	$(BANDIT) -r $(BACKEND_DIR)/app/ -c pyproject.toml
	$(PIP_AUDIT) --strict

.PHONY: clean
clean:  ## remove build artifacts and caches
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -prune -exec rm -rf {} +
	find . -type d -name '.ruff_cache' -prune -exec rm -rf {} +
	rm -rf build/ dist/ *.egg-info var/logs
	cd $(FRONTEND_DIR) && rm -rf node_modules/ dist/ .vite/ coverage/

# ============================================================================
# Docker
# ============================================================================
.PHONY: build
build:  ## build production images
	$(COMPOSE_PROD) build

.PHONY: up
up:  ## start production stack
	$(COMPOSE_PROD) up -d

.PHONY: down
down:  ## stop production stack
	$(COMPOSE_PROD) down

.PHONY: logs
logs:  ## tail production stack logs
	$(COMPOSE_PROD) logs -f --tail=200

# ============================================================================
# Operations
# ============================================================================
.PHONY: backup
backup:  ## snapshot Postgres + storage metadata
	bash $(DEPLOY_DIR)/scripts/backup.sh

.PHONY: restore
restore:  ## restore from latest backup (usage: make restore FILE=...)
	bash $(DEPLOY_DIR)/scripts/restore.sh $(FILE)

.PHONY: health
health:  ## check service health
	bash $(DEPLOY_DIR)/scripts/healthcheck.sh

.PHONY: docs-serve
docs-serve:  ## serve MkDocs locally
	$(PYTHON) -m mkdocs serve -a 0.0.0.0:8001
