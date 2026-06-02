# DocFormatConverter 项目收尾 — 验收清单

> 所有 checkpoints 必须通过，项目才视为完成。

---

## 代码修复
- [ ] `registry.py` 包含 `adjacency_list()` 方法且 `/v1/formats/convertible` 返回正确数据
- [ ] `frontend/Dockerfile` 使用 pnpm（非 npm）构建
- [ ] `backend/alembic.ini` 配置完整，`alembic upgrade head` 成功
- [ ] 所有 worker 任务模块（cleanup, webhook, maintenance）有完整实现
- [ ] 所有前端 UI 基础组件已创建（Button, Input, Select, Card, Modal, Toast, ProgressBar, Badge, Tabs, Dropdown, Switch, Skeleton）

## 代码质量
- [ ] `ruff check backend/` 无错误
- [ ] `black --check backend/` 全部通过
- [ ] `mypy backend/` 无类型错误
- [ ] `pnpm typecheck` 前端 TS 检查通过
- [ ] 无循环导入、缺失 import 错误

## 构建验证
- [ ] `pnpm build` 前端构建成功，产物 < 1MB gzip
- [ ] `docker build -f frontend/Dockerfile ./frontend` 成功
- [ ] `docker build -t docconv-api .` 后端镜像构建成功
- [ ] `docker build -f Dockerfile.converters -t docconv-converters .` 成功

## 运行时验证
- [ ] `python -c "from app.main import create_app; app = create_app()"` 无错误
- [ ] `curl http://localhost:8000/healthz` 返回 `{"status": "ok"}`
- [ ] `curl http://localhost:8000/v1/formats` 返回格式列表
- [ ] `curl http://localhost:8000/v1/formats/convertible` 返回边列表
- [ ] WebSocket `/ws/tasks/{task_id}` 可连接并接收进度消息
- [ ] 文件上传 → 转换 → 下载端到端流程可用

## Docker Compose
- [ ] `docker compose -f docker-compose.dev.yml up` 所有服务 healthy
- [ ] `docker compose up -d` 生产栈所有服务 healthy
- [ ] Celery worker 启动无 import 错误
- [ ] Celery beat 定时任务正常注册

## 安全
- [ ] `make security-scan` 无高危漏洞
- [ ] CORS 生产配置不允许 `*`
- [ ] Docker 容器以非 root 用户运行
- [ ] `.env.example` 所有配置项完整
- [ ] 无硬编码密钥/密码

## 测试
- [ ] `make test` 后端 pytest 全部通过
- [ ] `pnpm test` 前端 vitest 全部通过
- [ ] 核心模块测试覆盖率 ≥ 60%

## 最终检查
- [ ] `make lint` 全部通过
- [ ] `make test` 全部通过
- [ ] `make security-scan` 全部通过
- [ ] 一键部署流程文档可操作