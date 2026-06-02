# DocFormatConverter — 重构实施计划

> 状态: 进行中  
> 目标: 把"只有 8 个配置 + 6 个 spec、零代码"的仓库, 重构为生产可用的文档转换与处理平台。

---

## 0. 对旧仓库的诊断

旧仓库的实情:
- `app.py` / `src/` / `converters/` 全部不存在, 没有任何可运行代码
- `requirements.txt` 同时列了 Flask 和 FastAPI, `Dockerfile` 又按 Flask 启动 (`gunicorn app:app`), 自相矛盾
- `wkhtmltopdf` 已于 2023 年停止维护, 多个未修复 CVE, 不可再用
- `PyPDF2` 维护停滞, 改用 `pypdf`
- `config.yaml` 安全配置等于无: `cors_origins: "*"`, `api_key_enabled: false`
- `docker-compose.yml` 数据库密码明文 `password`
- 没有魔数校验, 没有任何速率限制实现, 没有任何沙箱设计
- 但 `spec/` 6 个文档写得很细, 方向是对的, 可以继承下来作为产品需求基线

本计划对照原 `spec/` 在实现层做了 6 处关键升级, 其余结构沿用:

| 维度 | 旧 spec | 本次重构 |
|------|--------|----------|
| Web 框架 | 含糊 (Flask + FastAPI 都列了) | **FastAPI (异步)** 统一 |
| 异步驱动 | Celery 同步 worker | Celery + gevent, 关键路径 FastAPI async |
| 密码哈希 | 未指定 | **Argon2id** (OWASP 推荐) |
| JWT 算法 | 含糊 | **RS256**, 私钥签名公钥验签, 密钥对启动时生成/挂载 |
| 存储 | 仅 S3 | **Storage 抽象 + Local/MinIO 双适配**, 配置切换 |
| 沙箱 | 提到 Docker/Firejail | 落地为 **subprocess + rlimits + seccomp(可选) + 临时目录**, 实际可用 |
| 病毒扫描 | 可选 | **ClamAV 集成, 默认关闭, 配 env 即开** |
| 速率限制 | 仅描述 | **slowapi 落地**, IP/用户/Key 三维度 |
| 依赖管理 | requirements.txt | **pyproject.toml + uv/pip 兼容** |
| 前端 | React 18 + Vite | **Vite + React 18 + TS 严格模式 + Tailwind + Zustand** |
| 可观测性 | 描述 | **structlog + Prometheus + /healthz /readyz /metrics** |
| 配置 | YAML | **Pydantic Settings + .env**, YAML 解析保留 |

---

## 1. 目录最终结构

```
DocFormatConverter/
├── PLAN.md                    ← 本文件
├── README.md
├── CHANGELOG.md
├── LICENSE
├── CONTRIBUTING.md
├── Makefile
├── pyproject.toml             ← 后端依赖与工具配置 (uv/poetry/pip 皆可)
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .editorconfig
├── Dockerfile                 ← 多阶段生产镜像
├── Dockerfile.dev             ← 开发热重载
├── docker-compose.yml         ← 生产
├── docker-compose.dev.yml     ← 开发
│
├── docs/                      ← 用户文档 (产品/部署/运维/API)
│   ├── README.md
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   ├── security.md
│   ├── operations.md
│   └── ui-design.md
│
├── spec/                      ← 原仓库的设计规范 (沿用)
│   ├── design.md
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── ui-design.md
│   └── tasks.md
│
├── archive/                   ← 旧仓库的占位文件, 避免混淆
│   ├── README.md
│   ├── config.yaml
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 ← FastAPI 入口
│   │   ├── settings.py             ← Pydantic Settings
│   │   ├── logging_config.py
│   │   ├── exceptions.py
│   │   ├── deps.py
│   │   ├── lifespan.py
│   │   │
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── auth.py
│   │   │       ├── convert.py
│   │   │       ├── batch.py
│   │   │       ├── tasks.py
│   │   │       ├── files.py
│   │   │       ├── users.py
│   │   │       ├── formats.py
│   │   │       ├── admin.py
│   │   │       └── ws.py
│   │   │
│   │   ├── core/
│   │   │   ├── security.py         ← Argon2, JWT, API Key
│   │   │   ├── permissions.py
│   │   │   ├── rate_limit.py
│   │   │   ├── magic_bytes.py
│   │   │   ├── sanitizers.py
│   │   │   ├── signing.py          ← Webhook HMAC
│   │   │   └── antivirus.py
│   │   │
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/
│   │   │       ├── user.py
│   │   │       ├── api_key.py
│   │   │       ├── task.py
│   │   │       ├── batch.py
│   │   │       ├── file.py
│   │   │       ├── task_log.py
│   │   │       ├── audit_log.py
│   │   │       └── webhook.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── auth.py
│   │   │   ├── task.py
│   │   │   ├── file.py
│   │   │   ├── user.py
│   │   │   └── format.py
│   │   │
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── api_key_service.py
│   │   │   ├── task_service.py
│   │   │   ├── batch_service.py
│   │   │   ├── upload_service.py
│   │   │   ├── download_service.py
│   │   │   ├── storage_service.py
│   │   │   ├── webhook_service.py
│   │   │   └── audit_service.py
│   │   │
│   │   ├── storage/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   ├── s3.py
│   │   │   └── factory.py
│   │   │
│   │   ├── converters/
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── factory.py
│   │   │   ├── options.py
│   │   │   ├── result.py
│   │   │   ├── detection.py
│   │   │   ├── sandbox.py
│   │   │   ├── backends/
│   │   │   │   ├── libreoffice.py
│   │   │   │   ├── pandoc.py
│   │   │   │   ├── weasyprint_backend.py
│   │   │   │   ├── pillow_backend.py
│   │   │   │   └── tesseract.py
│   │   │   ├── document/
│   │   │   ├── spreadsheet/
│   │   │   ├── presentation/
│   │   │   ├── markup/
│   │   │   ├── data/
│   │   │   ├── image/
│   │   │   └── ebook/
│   │   │
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── conversion.py
│   │   │   ├── cleanup.py
│   │   │   ├── webhook.py
│   │   │   └── progress.py
│   │   │
│   │   ├── websocket/
│   │   │   ├── manager.py
│   │   │   └── routes.py
│   │   │
│   │   ├── middleware/
│   │   │   ├── request_id.py
│   │   │   ├── security_headers.py
│   │   │   └── error_handler.py
│   │   │
│   │   └── observability/
│   │       ├── metrics.py
│   │       └── tracing.py
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_settings.py
│   │   ├── test_security.py
│   │   ├── test_magic_bytes.py
│   │   ├── test_format_registry.py
│   │   ├── test_converter_dispatch.py
│   │   ├── test_storage.py
│   │   ├── test_api_auth.py
│   │   ├── test_api_convert.py
│   │   ├── test_api_tasks.py
│   │   ├── test_rate_limit.py
│   │   └── fixtures/
│   │
│   └── scripts/
│       ├── bootstrap_admin.py
│       ├── create_api_key.py
│       └── generate_jwt_keys.py
│
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml   (pnpm 优先, npm/yarn 兼容)
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.cjs
│   ├── index.html
│   ├── Dockerfile
│   ├── nginx.conf       ← 前端容器内 nginx 配置
│   ├── public/
│   │   ├── favicon.svg
│   │   └── robots.txt
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── i18n/
│   │   │   ├── index.ts
│   │   │   ├── en.ts
│   │   │   └── zh.ts
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── convert.ts
│   │   │   ├── batch.ts
│   │   │   ├── tasks.ts
│   │   │   ├── files.ts
│   │   │   ├── users.ts
│   │   │   ├── formats.ts
│   │   │   └── ws.ts
│   │   ├── stores/
│   │   │   ├── authStore.ts
│   │   │   ├── themeStore.ts
│   │   │   └── taskStore.ts
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useTaskProgress.ts
│   │   │   ├── useFormats.ts
│   │   │   └── useToast.ts
│   │   ├── components/
│   │   │   ├── layout/{Header,Footer,Sidebar,Layout}.tsx
│   │   │   ├── ui/{Button,Input,Select,Card,Modal,Toast,ProgressBar,Spinner,Badge,Tabs,Dropdown,Switch,Skeleton}.tsx
│   │   │   ├── upload/{Dropzone,FileListItem}.tsx
│   │   │   ├── conversion/{FormatSelector,OptionsPanel,ConversionProgress,BatchProgress}.tsx
│   │   │   └── auth/{LoginForm,RegisterForm,ProtectedRoute}.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── ConvertPage.tsx
│   │   │   ├── BatchPage.tsx
│   │   │   ├── TasksPage.tsx
│   │   │   ├── TaskDetailPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── ProfilePage.tsx
│   │   │   ├── ApiKeysPage.tsx
│   │   │   ├── DocsPage.tsx
│   │   │   ├── NotFoundPage.tsx
│   │   │   └── ErrorPage.tsx
│   │   ├── utils/{format,validation,download,errors}.ts
│   │   ├── types/{api,user,task,format}.ts
│   │   └── styles/globals.css
│   └── tests/
│       ├── setup.ts
│       └── basic.test.ts
│
├── deploy/
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── conf.d/
│   │       └── default.conf
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alert.rules.yml
│   ├── grafana/
│   │   └── dashboards/
│   │       └── api.json
│   ├── k8s/
│   │   ├── namespace.yml
│   │   ├── api-deployment.yml
│   │   ├── worker-deployment.yml
│   │   ├── beat-deployment.yml
│   │   ├── frontend-deployment.yml
│   │   ├── postgres-sts.yml
│   │   ├── redis-sts.yml
│   │   ├── minio-sts.yml
│   │   ├── ingress.yml
│   │   ├── hpa.yml
│   │   ├── pvc.yml
│   │   ├── configmap.yml
│   │   └── secret.example.yml
│   ├── scripts/
│   │   ├── backup.sh
│   │   ├── restore.sh
│   │   ├── init-minio.sh
│   │   └── healthcheck.sh
│   └── systemd/
│       └── docconverter.service
│
└── .github/
    └── workflows/
        ├── backend-ci.yml
        ├── frontend-ci.yml
        ├── docker-image.yml
        └── security-scan.yml
```

---

## 2. 关键设计决策

### 2.1 进程模型

```
            ┌────────────────────┐
            │   Nginx (TLS/WAF)  │  1 容器
            └─────────┬──────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
   ┌────▼────────┐           ┌──────▼───────┐
   │  Frontend   │           │  FastAPI API │  N 副本
   │  (static)   │           │  (uvicorn)   │
   └─────────────┘           └──────┬───────┘
                                   │
                                   ▼
                            ┌─────────────┐
                            │  Celery     │  N 副本
                            │  Workers    │
                            └──────┬──────┘
                                   │
        ┌──────────────┬───────────┴──────────┬───────────────┐
        ▼              ▼                      ▼               ▼
   ┌────────┐   ┌──────────┐         ┌──────────────┐  ┌──────────┐
   │ Postgres│   │  Redis   │         │   MinIO/S3   │  │  ClamAV  │
   └────────┘   └──────────┘         └──────────────┘  └──────────┘
```

- API 与 Worker 共享代码, 通过 `PYTHONPATH=backend` 部署
- Worker 通过 Celery 信号把进度推入 Redis Pub/Sub, API 进程订阅后通过 WebSocket 推给前端
- 转换通过 `subprocess.run([...], timeout=, preexec_fn=...)` 加 `resource.setrlimit` 实现 CPU/内存/Fsize 限制, 工作目录在临时 tmpfs 上

### 2.2 格式支持矩阵 (实现目标)

| 类别     | 源                          | 主要目标                              | 后端                        |
|----------|-----------------------------|---------------------------------------|-----------------------------|
| Document | pdf, docx, doc, odt, rtf, epub, mobi | 同类/HTML/MD/TXT/图片              | LibreOffice, pdf2image, pdfplumber, pypdf, pypandoc, ebooklib |
| Spreadsheet | xlsx, xls, csv, tsv, ods  | csv, xlsx, json, html, pdf            | openpyxl, pandas, xlrd, odfpy, LibreOffice |
| Presentation | pptx, ppt, odp        | pdf, png(slide), html, pptx           | python-pptx, pdf2image, LibreOffice |
| Markup   | md, html, rst               | html, pdf, docx, md                   | pypandoc, weasyprint, markdown |
| Data     | json, xml, yaml, csv, toml  | json, xml, yaml, csv, xlsx, toml      | 原生 + pandas |
| Image    | png, jpg, jpeg, webp, gif, bmp, tiff, svg, heic | png, jpg, webp, pdf, tiff        | Pillow, pillow-heif, cairosvg |
| Ebook    | epub, mobi, azw3            | pdf, epub, txt, html                  | ebooklib, pypandoc, LibreOffice |

所有可走 LibreOffice 的统一走 headless 模式, 渲染参数从 `ConversionOptions` 注入。

### 2.3 安全模型

- 密码: Argon2id (`argon2-cffi`), 默认 time_cost=3, memory_cost=64MB
- JWT: RS256, 私钥仅 API 进程持有, 公钥可下发用于多服务验签, 启动时若未发现密钥对则自动生成
- API Key: 32 字节随机, base62 编码, 库内仅存 `SHA-256(key)`, 创建时**明文只返回一次**
- 速率限制: `slowapi` + Redis 后端, 三维度 (IP/用户/Key), 失败 429 + Retry-After
- 文件上传: 扩展名 + 魔数双重校验, 白名单格式, 拒绝可执行/MIME 嗅探攻击
- 病毒扫描: 可选 ClamAV (`clamd` 协议), 默认关闭, 通过 `ANTIVIRUS_ENABLED=1` 开启
- CORS: 白名单 (`CORS_ALLOW_ORIGINS=...`), 不接受 `*` 在生产
- 安全头: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy` (前端)
- 容器: API/Worker 以非 root 用户运行, `/tmp` 单独挂载 tmpfs, 文件名严格白名单
- 路径穿越: 任何 `os.path.join` 都过 `safe_join`, 校验不超出 storage root

### 2.4 配置矩阵 (env)

| 变量 | 默认 | 说明 |
|------|------|------|
| `APP_ENV` | dev | dev/staging/prod |
| `APP_NAME` | DocFormatConverter | |
| `API_HOST` | 0.0.0.0 | |
| `API_PORT` | 8000 | |
| `API_WORKERS` | 4 | |
| `DATABASE_URL` | postgresql+asyncpg://... | 必填 |
| `DATABASE_POOL_SIZE` | 10 | |
| `REDIS_URL` | redis://redis:6379/0 | 必填 |
| `JWT_PRIVATE_KEY_PATH` | ./keys/jwt_private.pem | 自动生成 |
| `JWT_PUBLIC_KEY_PATH` | ./keys/jwt_public.pem | |
| `JWT_ACCESS_TTL_MIN` | 30 | |
| `JWT_REFRESH_TTL_DAY` | 30 | |
| `STORAGE_BACKEND` | local | local / s3 |
| `STORAGE_LOCAL_ROOT` | ./var/storage | |
| `S3_ENDPOINT_URL` | http://minio:9000 | |
| `S3_ACCESS_KEY` | | |
| `S3_SECRET_KEY` | | |
| `S3_BUCKET` | conversions | |
| `MAX_FILE_SIZE_MB` | 100 | |
| `MAX_BATCH_FILES` | 100 | |
| `MAX_CONVERSION_TIMEOUT_S` | 300 | |
| `RATE_LIMIT_DEFAULT` | 100/minute | |
| `RATE_LIMIT_CONVERT` | 10/minute | |
| `CORS_ALLOW_ORIGINS` | http://localhost:5173 | 逗号分隔 |
| `ANTIVIRUS_ENABLED` | false | |
| `ANTIVIRUS_HOST` | clamav | |
| `LOG_LEVEL` | INFO | |
| `LOG_FORMAT` | json | json / console |

---

## 3. 实施阶段

| 阶段 | 任务 | 状态 |
|------|------|------|
| 0 | 总体规划 + 项目结构 | ✅ |
| 1 | 基础设施 (pyproject, settings, logging, exceptions) | ⏳ |
| 2 | 数据库 (模型 + Alembic) | ⏳ |
| 3 | 安全核心 (Argon2, JWT, API Key, 限流, 魔数) | ⏳ |
| 4 | 存储 (Local + S3 适配) | ⏳ |
| 5 | 转换引擎 (基类 + 后端 + 各分类实现) | ⏳ |
| 6 | Workers (Celery 任务) | ⏳ |
| 7 | API 路由 (auth/convert/batch/tasks/files/users/admin/ws) | ⏳ |
| 8 | 中间件 + 可观测性 | ⏳ |
| 9 | 前端基础设施 + 组件库 | ⏳ |
| 10 | 前端页面 + WebSocket | ⏳ |
| 11 | Docker (多阶段 + Compose dev/prod) | ⏳ |
| 12 | 部署 (Nginx, Prometheus, K8s, 备份) | ⏳ |
| 13 | CI/CD + pre-commit | ⏳ |
| 14 | 测试 (pytest + vitest) | ⏳ |
| 15 | 文档收尾 | ⏳ |

---

## 4. 验收标准 (本次重构完成时)

- [ ] `docker compose -f docker-compose.dev.yml up` 一键起开发环境
- [ ] `docker compose up -d` 一键起生产栈 (含 Prometheus/Grafana/MinIO)
- [ ] `curl -F file=@x.pdf -F target_format=docx http://api/v1/convert` 同步返回任务 ID
- [ ] WebSocket 推送实时进度百分比
- [ ] 转换完成后 `GET /v1/files/{id}/download` 流式下载
- [ ] 速率限制生效: 第 11 次 1 分钟内请求 `/convert` 返回 429
- [ ] 后端 pytest 覆盖率 ≥ 60% (核心模块 ≥ 80%)
- [ ] 前端 `pnpm build` 产物 < 1MB gzip
- [ ] `make lint` 全部通过 (black/ruff/mypy/eslint)
- [ ] `make test` 全部通过
- [ ] `make security-scan` 无高危漏洞
- [ ] `kubectl apply -f deploy/k8s/` 可成功部署
- [ ] README 含一键部署/快速开始/API 示例/常见问题
