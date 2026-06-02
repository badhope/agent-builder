# 项目收尾 Tasks

> 基于 spec.md 中识别的断层问题，按依赖顺序执行。每个 Task 产出可验证的结果。

---

## Task 1: 修复 ConverterRegistry.adjacency_list() 方法
- **描述**: `registry.py` 中缺少 `adjacency_list()` 方法，导致 `/v1/formats/convertible` API 端点崩溃。
- **文件**: `backend/app/converters/registry.py`
- [ ] 在 `ConverterRegistry` 类中添加 `adjacency_list()` 方法，返回 `list[dict]` 格式的边列表
- [ ] 验证 `GET /v1/formats/convertible` 返回正确的 JSON 响应
- **验收**: curl 调用返回完整 edges 列表

## Task 2: 修复前端 Dockerfile 使用 pnpm
- **描述**: `frontend/Dockerfile` 引用了 `package-lock.json`，但项目使用 pnpm 且只有 `pnpm-lock.yaml`。
- **文件**: `frontend/Dockerfile`
- [ ] 将 Dockerfile 改为使用 pnpm（安装 pnpm、使用 pnpm install、pnpm build）
- [ ] 更新 COPY 指令引用正确的锁文件
- [ ] 确保多阶段构建正常，最终 nginx 镜像可运行
- **验收**: `docker build -f frontend/Dockerfile ./frontend` 成功

## Task 3: 修复合规检查（后端 lint/typecheck）
- **描述**: 运行 ruff、black、mypy 检查后端代码，修复所有报错。
- **文件**: 整个 `backend/` 目录
- [ ] 运行 `ruff check backend/` 并修复所有错误
- [ ] 运行 `black --check backend/` 并格式化所有文件
- [ ] 运行 `mypy backend/` 并修复所有类型错误
- [ ] 修复所有 Python import 错误（循环导入、缺失导入等）
- [ ] 确保 `pyproject.toml` 中依赖与代码实际使用一致
- **验收**: `make lint` 全部通过

## Task 4: 补全前端 UI 基础组件
- **描述**: 前端页面引用了 Button、Input、Select、Card、Modal、Toast、ProgressBar、Badge 等组件，需要确认全部存在且有完整实现。缺失的组件需要补全。
- **文件**: `frontend/src/components/ui/`
- [ ] 审查所有页面引用的组件（Button, Input, Select, Card, Modal, Toast, ProgressBar, Badge, Tabs, Dropdown, Switch, Skeleton）
- [ ] 对缺失的组件创建实现（使用 Tailwind CSS + clsx/tailwind-merge）
- [ ] 确保所有组件的 TypeScript 类型正确
- [ ] 确保组件样式与现有设计一致
- **验收**: 所有页面不再因缺失组件而报 import 错误

## Task 5: 修复前端 TypeScript 编译和构建
- **描述**: 确保前端 TypeScript 类型检查和 Vite 构建通过。
- **文件**: `frontend/`
- [ ] 运行 `pnpm typecheck` 并修复所有 TS 错误
- [ ] 运行 `pnpm build` 确保 Vite 构建成功
- [ ] 修复所有 API client 类型不匹配问题
- [ ] 确保构建产物 < 1MB gzip
- **验收**: `pnpm typecheck && pnpm build` 全部通过

## Task 6: 验证并补全 Worker 任务模块
- **描述**: Celery 配置引用了 cleanup、webhook、maintenance 等 worker 模块，需确认它们有实际实现。
- **文件**: `backend/app/workers/cleanup.py`, `backend/app/workers/webhook.py`, `backend/app/workers/maintenance.py`
- [ ] 审查 cleanup.py 是否包含所有被引用的任务（expire_old_tasks, purge_expired_files, purge_idempotency_records, requeue_stuck_tasks, refresh_metrics）
- [ ] 审查 webhook.py 是否包含 deliver_pending 任务
- [ ] 审查 maintenance.py 是否包含 recompute_storage_quotas, detect_orphan_files 任务
- [ ] 对缺失的任务补全实现
- **验收**: Celery worker 启动时无 import 错误，所有任务注册成功

## Task 7: 验证后端 Alembic 配置完整性
- **描述**: 确认 `backend/alembic.ini` 配置完整可用，迁移脚本正确。
- **文件**: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_schema.py`
- [ ] 检查 alembic.ini 是否有正确的 sqlalchemy.url 和 script_location
- [ ] 检查 env.py 是否正确加载所有模型和配置
- [ ] 检查 0001_initial_schema.py 是否创建了所有必需的数据库表
- [ ] 如缺失则补全
- **验收**: `alembic upgrade head` 成功创建所有表

## Task 8: 端到端集成修复
- **描述**: 修复所有跨模块引用问题，确保整个调用链（API → Dispatcher → Celery → Converter → Storage）完整工作。
- **文件**: 整个项目
- [ ] 验证所有 FastAPI 依赖注入链完整（deps.py, api/deps.py 等）
- [ ] 验证 WebSocket 路由与 manager 配合正确
- [ ] 验证 storage 工厂能正确实例化 local/S3 后端
- [ ] 验证 converter_dispatcher 的 enqueue → Celery task 链路
- [ ] 修复所有运行时 import 路径问题
- **验收**: `python -c "from app.main import create_app; app = create_app()"` 无错误

## Task 9: 前端页面交互完善
- **描述**: 确保所有前端页面功能完整、API 调用正常、错误处理到位。
- **文件**: `frontend/src/pages/`, `frontend/src/api/`
- [ ] 审查 ConvertPage 的完整上传→转换→结果流程
- [ ] 审查 TasksPage 的实时进度更新（WebSocket）
- [ ] 审查 DashboardPage 的数据获取
- [ ] 审查所有页面的 loading/error/empty 状态处理
- [ ] 修复前端 API client 的路径和类型匹配后端
- **验收**: 所有页面在 mock 数据下渲染正常

## Task 10: Docker 环境验证和修复
- **描述**: 验证 Docker Compose 开发和生产环境配置，确保所有服务可正常启动。
- **文件**: `Dockerfile`, `Dockerfile.dev`, `Dockerfile.converters`, `docker-compose.yml`, `docker-compose.dev.yml`
- [ ] 验证 Dockerfile 构建过程和路径正确
- [ ] 验证 Dockerfile.dev 热重载配置有效
- [ ] 验证 docker-compose.dev.yml 所有服务依赖和健康检查
- [ ] 验证 docker-compose.yml 生产配置完整
- [ ] 修复所有 Docker 构建报错
- **验收**: `docker compose -f docker-compose.dev.yml up` 所有服务健康

## Task 11: 测试验证
- **描述**: 确保后端 pytest 和前端 vitest 测试可以运行并通过。
- **文件**: `backend/tests/`, `frontend/src/test/`
- [ ] 运行后端测试并修复失败用例
- [ ] 运行前端测试并修复失败用例
- [ ] 确保测试覆盖率满足基本要求
- **验收**: `make test` 和 `pnpm test` 全部通过

## Task 12: 安全扫描和最终验证
- **描述**: 运行安全扫描并确保无高危漏洞，做最终完整性检查。
- [ ] 运行 `make security-scan` 修复高危问题
- [ ] 验证 .env.example 配置项完整
- [ ] 确保没有硬编码的密钥/密码
- [ ] 确保 CORS 配置不允许 `*` 在生产模式
- [ ] 验证所有 Docker 容器以非 root 运行
- **验收**: `make security-scan` 通过，安全基线达标

---

# Task Dependencies
- **Task 1** (registry fix) — 无依赖，可立即开始
- **Task 2** (Dockerfile pnpm) — 无依赖，可立即开始
- **Task 3** (lint/typecheck) — 依赖 Task 1（registry 修复会影响 typecheck）
- **Task 4** (UI 组件) — 无依赖，可立即开始
- **Task 5** (前端构建) — 依赖 Task 4（组件补全后才能过 build）
- **Task 6** (worker 模块) — 无依赖，可立即开始
- **Task 7** (alembic) — 无依赖，可立即开始
- **Task 8** (端到端集成) — 依赖 Task 1, 3, 6, 7
- **Task 9** (前端页面) — 依赖 Task 4, 5
- **Task 10** (Docker 验证) — 依赖 Task 2, 3, 5
- **Task 11** (测试) — 依赖 Task 1-9
- **Task 12** (安全扫描) — 依赖 Task 1-11

Task 1, 2, 4, 6, 7 可并行执行。