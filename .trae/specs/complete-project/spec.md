# DocFormatConverter 项目收尾 Spec

## Why
项目已经完成了约 85% 的实现工作，但存在多处代码断层和集成缺陷，导致项目无法实际运行。需要在现有基础上修复关键问题、补全缺失模块、打通端到端流程，确保 `docker compose up` 一键启动成功，所有核心功能正常工作。

## What Changes
- 修复 `registry.py` 缺少 `adjacency_list()` 方法导致 `/v1/formats/convertible` 路由崩溃
- 修复前端 Dockerfile 引用 `package-lock.json` 但项目使用 `pnpm` 导致的构建失败
- 补全后端 `alembic.ini` 配置（如缺失则为 stub）
- 验证并修复后端 worker 任务模块（cleanup.py, webhook.py, maintenance.py）的实现完整性
- 修复所有 TypeScript/Python import 错误和类型检查问题
- 确保前端 `pnpm build` 通过且产物 < 1MB gzip
- 确保后端 `make lint`（ruff + black + mypy）全部通过
- 确保 Docker Compose 开发/生产环境一键启动成功
- 补全缺失的前端 UI 组件（Button, Input, Select, Card, Modal, Toast 等基础组件）
- 确保 WebSocket 实时进度推送端到端可用
- 确保所有测试可以通过（pytest + vitest）
- 确保 `make security-scan` 无高危漏洞

## Impact
- Affected specs: 所有 15 个 PLAN.md 阶段（Phase 0-15）
- Affected code: `backend/app/converters/registry.py`, `frontend/Dockerfile`, `backend/alembic.ini`, `backend/app/workers/*.py`, `frontend/src/components/ui/*.tsx`, `frontend/package.json`, `pyproject.toml`

## ADDED Requirements

### Requirement: Registry adjacency list support
The ConverterRegistry SHALL expose an `adjacency_list()` method that returns all supported (source, target, quality, backend) edges as a serialisable list of dicts.

#### Scenario: Formats convertible endpoint works
- **WHEN** `GET /v1/formats/convertible` is requested
- **THEN** response returns `{"edges": [...]}` with all supported conversion pairs

### Requirement: Frontend Docker build with pnpm
The frontend Dockerfile SHALL use pnpm (not npm) as the package manager to match the project's pnpm-lock.yaml.

#### Scenario: Frontend Docker image builds successfully
- **WHEN** `docker build -f frontend/Dockerfile ./frontend` is executed
- **THEN** the image builds without error and serves the frontend on port 80

### Requirement: Complete UI component library
The frontend SHALL have all basic UI components implemented: Button, Input, Select, Card, Modal, Toast, ProgressBar, Badge, Tabs, Dropdown, Switch, Skeleton.

#### Scenario: All UI components render without error
- **WHEN** any page using UI components is loaded
- **THEN** all components render correctly with proper Tailwind styling

### Requirement: Worker task modules complete
All Celery worker task modules referenced in `celery_app.py` SHALL have actual implementations (not stubs).

#### Scenario: Celery workers start without import errors
- **WHEN** `celery -A app.workers.celery_app worker` is started
- **THEN** all task modules load successfully and tasks can be dispatched

### Requirement: Alembic configuration complete
The `backend/alembic.ini` SHALL be a complete, valid Alembic configuration pointing to the correct database and migration directory.

#### Scenario: Database migration runs successfully
- **WHEN** `alembic upgrade head` is executed
- **THEN** all tables are created without error

### Requirement: Docker Compose one-click startup
`docker compose -f docker-compose.dev.yml up` SHALL start all services (API, worker, beat, Postgres, Redis, MinIO, frontend) without errors.

#### Scenario: Dev environment starts successfully
- **WHEN** `docker compose -f docker-compose.dev.yml up` is run
- **THEN** all health checks pass and API responds on http://localhost:8000/healthz

### Requirement: Production Docker Compose startup
`docker compose up -d` SHALL start the full production stack with all services healthy.

#### Scenario: Production stack starts successfully
- **WHEN** `docker compose up -d` is run  
- **THEN** all services pass health checks and API responds on http://localhost:8000/healthz

### Requirement: End-to-end conversion flow
A complete conversion flow SHALL work: upload file → create conversion task → async processing → download result → WebSocket progress updates.

#### Scenario: User uploads and converts a file
- **WHEN** user uploads a .docx file and requests conversion to .pdf via API
- **THEN** task is created, worker processes it, result is stored, and WebSocket pushes progress updates

### Requirement: Code quality checks pass
All linting, type checking, and formatting SHALL pass without errors.

#### Scenario: make lint succeeds
- **WHEN** `make lint` is executed
- **THEN** ruff, black, and mypy all pass without errors

### Requirement: Frontend build succeeds
The frontend TypeScript build SHALL complete without errors and produce optimized output.

#### Scenario: pnpm build succeeds
- **WHEN** `cd frontend && pnpm build` is executed
- **THEN** TypeScript compilation and Vite build succeed, output < 1MB gzip

### Requirement: Security scan passes
Security scanning SHALL find no high-severity vulnerabilities.

#### Scenario: make security-scan succeeds
- **WHEN** `make security-scan` is executed
- **THEN** bandit finds no high-severity issues and pip-audit reports no critical vulns