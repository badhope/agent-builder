# DocFormatConverter - 技术架构文档

> **版本**: 1.0.0  
> **日期**: 2026-05-18  
> **架构风格**: 微服务 + 事件驱动  
> **部署模式**: 容器化 / Serverless Ready

---

## 1. 系统架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端层 (Client Layer)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │   Web App   │  │   Mobile    │  │   CLI Tool  │  │  Third-party    │   │
│   │   (React)   │  │  (PWA)      │  │  (Python)   │  │    Apps         │   │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │
│          │                │                │                  │            │
│          └────────────────┴────────────────┴──────────────────┘            │
│                                    │                                        │
│                         HTTPS / HTTP2 / WebSocket                          │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                         API 网关层 (API Gateway)                            │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│   ┌────────────────────────────────┴────────────────────────────────┐       │
│   │                        Nginx / Traefik                         │       │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐ │       │
│   │  │   SSL/TLS   │  │ Rate Limit  │  │    CORS     │  │  WAF   │ │       │
│   │  │  Termination│  │   (Redis)   │  │   Headers   │  │        │ │       │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └────────┘ │       │
│   └────────────────────────────────┬────────────────────────────────┘       │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                      应用服务层 (Application Layer)                         │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│   ┌────────────────────────────────┴────────────────────────────────┐       │
│   │                      FastAPI Application                         │       │
│   │                                                                  │       │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐  │       │
│   │  │   Auth      │  │   Upload    │  │   Convert   │  │ Status │  │       │
│   │  │   Module    │  │   Module    │  │   Module    │  │ Module │  │       │
│   │  │  (JWT/API)  │  │ (Streaming) │  │  (Async)    │  │(WS/SSE)│  │       │
│   │  └─────────────┘  └─────────────┘  └──────┬──────┘  └────────┘  │       │
│   │                                           │                     │       │
│   │  ┌────────────────────────────────────────┘                     │       │
│   │  │                                                              │       │
│   │  │              Celery Task Queue (Redis)                       │       │
│   │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │       │
│   │  │  │ Worker 1│  │ Worker 2│  │ Worker 3│  │ Worker N│         │       │
│   │  │  │(Convert)│  │(Convert)│  │(Convert)│  │(Convert)│         │       │
│   │  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘         │       │
│   │  │       └─────────────┴─────────────┴─────────────┘            │       │
│   │  └──────────────────────────────────────────────────────────────┘       │
│   └─────────────────────────────────────────────────────────────────────────┘
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                      核心引擎层 (Core Engine Layer)                         │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│   ┌────────────────────────────────┴────────────────────────────────┐       │
│   │                    Converter Engine (Python)                     │       │
│   │                                                                  │       │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐  │       │
│   │  │  Document   │  │ Spreadsheet │  │Presentation │  │  Data  │  │       │
│   │  │  Converter  │  │  Converter  │  │  Converter  │  │Converter│  │       │
│   │  │(LibreOffice)│  │(openpyxl)   │  │(python-pptx)│  │(Pandoc)│  │       │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └────────┘  │       │
│   │                                                                  │       │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐  │       │
│   │  │   Image     │  │   Markup    │  │   eBook     │  │ Archive│  │       │
│   │  │  Converter  │  │  Converter  │  │  Converter  │  │Converter│  │       │
│   │  │  (Pillow)   │  │  (pypandoc) │  │  (ebooklib) │  │(zipfile)│  │       │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └────────┘  │       │
│   │                                                                  │       │
│   │  ┌─────────────────────────────────────────────────────────┐     │       │
│   │  │              Sandbox Environment (Docker/Firejail)       │     │       │
│   │  │                    Resource Isolation                     │     │       │
│   │  └─────────────────────────────────────────────────────────┘     │       │
│   └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                      数据存储层 (Data Storage Layer)                        │
├────────────────────────────────────┼────────────────────────────────────────┤
│                                    │                                        │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │ PostgreSQL  │  │    Redis    │  │ Object Store│  │   File System   │   │
│   │  (Metadata) │  │  (Cache/    │  │  (S3/MinIO) │  │  (Local/Temp)   │   │
│   │             │  │   Queue)    │  │  (Files)    │  │                 │   │
│   │  - Users    │  │             │  │             │  │  - Uploads      │   │
│   │  - Tasks    │  │  - Sessions │  │  - Input    │  │  - Outputs      │   │
│   │  - API Keys │  │  - Rate Lim │  │  - Output   │  │  - Logs         │   │
│   │  - Audit    │  │  - Pub/Sub  │  │  - Backups  │  │                 │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 分层架构说明

| 层级 | 职责 | 技术栈 | 扩展性 |
|------|------|--------|--------|
| 客户端层 | 用户交互 | React, PWA, CLI | 水平扩展 |
| API网关层 | 流量管理 | Nginx, Traefik | 负载均衡 |
| 应用服务层 | 业务逻辑 | FastAPI, Celery | 自动扩缩容 |
| 核心引擎层 | 格式转换 | Python, LibreOffice | 资源池化 |
| 数据存储层 | 持久化 | PostgreSQL, Redis, S3 | 主从复制 |

---

## 2. 核心组件详解

### 2.1 API 服务 (FastAPI)

```python
# 架构代码示意
"""
app/
├── __init__.py
├── main.py                 # FastAPI 应用入口
├── config.py              # 配置管理
├── dependencies.py        # 依赖注入
├── middleware/
│   ├── __init__.py
│   ├── auth.py           # JWT/API Key 认证
│   ├── rate_limit.py     # 速率限制
│   ├── cors.py           # 跨域处理
│   └── logging.py        # 请求日志
├── routers/
│   ├── __init__.py
│   ├── auth.py           # 认证路由
│   ├── upload.py         # 文件上传
│   ├── convert.py        # 转换任务
│   ├── status.py         # 状态查询
│   ├── download.py       # 文件下载
│   └── admin.py          # 管理接口
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── upload_service.py
│   ├── convert_service.py
│   └── storage_service.py
└── models/
    ├── __init__.py
    ├── user.py
    ├── task.py
    └── file.py
"""
```

#### 2.1.1 路由设计

```yaml
API_Routes:
  public:
    - GET  /health          # 健康检查
    - GET  /formats         # 支持格式列表
    - POST /convert         # 单文件转换
    - POST /batch           # 批量转换
    
  authenticated:
    - GET  /tasks           # 任务列表
    - GET  /tasks/{id}      # 任务详情
    - DELETE /tasks/{id}    # 取消任务
    - GET  /files           # 文件列表
    - GET  /files/{id}      # 文件详情
    - GET  /files/{id}/download  # 下载文件
    
  admin:
    - GET  /admin/stats     # 系统统计
    - GET  /admin/users     # 用户管理
    - POST /admin/maintenance  # 维护模式
```

### 2.2 任务队列 (Celery + Redis)

```python
# Celery 配置
celery_config = {
    "broker_url": "redis://redis:6379/0",
    "result_backend": "redis://redis:6379/1",
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 600,  # 10分钟超时
    "worker_prefetch_multiplier": 1,  # 公平调度
    "task_routes": {
        "convert.*": {"queue": "conversion"},
        "cleanup.*": {"queue": "maintenance"},
    },
    "task_default_queue": "default",
}
```

#### 2.2.1 任务类型

```yaml
Task_Types:
  conversion:
    queue: "conversion"
    priority: 5
    retry_policy:
      max_retries: 3
      countdown: 60
      exponential_backoff: true
      
  cleanup:
    queue: "maintenance"
    priority: 1
    schedule: "0 */6 * * *"  # 每6小时
    
  notification:
    queue: "notifications"
    priority: 3
    retry_policy:
      max_retries: 5
```

### 2.3 转换引擎

```python
# 转换引擎架构
"""
engine/
├── __init__.py
├── base.py                 # 基础转换器类
├── registry.py            # 转换器注册表
├── factory.py             # 转换器工厂
├── document/              # 文档转换
│   ├── __init__.py
│   ├── pdf_converter.py
│   ├── docx_converter.py
│   └── odt_converter.py
├── spreadsheet/           # 表格转换
│   ├── __init__.py
│   ├── xlsx_converter.py
│   └── csv_converter.py
├── presentation/          # 演示转换
│   ├── __init__.py
│   └── pptx_converter.py
├── markup/                # 标记语言
│   ├── __init__.py
│   ├── markdown_converter.py
│   └── html_converter.py
├── data/                  # 数据格式
│   ├── __init__.py
│   ├── json_converter.py
│   └── xml_converter.py
├── image/                 # 图像转换
│   ├── __init__.py
│   └── image_converter.py
└── ebook/                 # 电子书
    ├── __init__.py
    └── epub_converter.py
"""
```

#### 2.3.1 转换器基类

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ConversionQuality(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LOSSLESS = "lossless"

@dataclass
class ConversionOptions:
    target_format: str
    quality: ConversionQuality = ConversionQuality.HIGH
    preserve_metadata: bool = True
    compress_output: bool = False
    custom_options: Dict[str, Any] = None

@dataclass
class ConversionResult:
    success: bool
    output_path: str
    file_size: int
    duration_ms: int
    metadata: Dict[str, Any]
    error_message: str = None

class BaseConverter(ABC):
    """所有转换器的基类"""
    
    supported_formats: Dict[str, List[str]] = {}
    
    @abstractmethod
    def convert(
        self,
        input_file: BinaryIO,
        options: ConversionOptions
    ) -> ConversionResult:
        """执行转换"""
        pass
    
    @abstractmethod
    def validate_input(self, file: BinaryIO) -> bool:
        """验证输入文件"""
        pass
    
    def get_supported_conversions(self, source_format: str) -> List[str]:
        """获取支持的目标格式"""
        return self.supported_formats.get(source_format, [])
```

### 2.4 沙箱环境

```yaml
Sandbox_Configuration:
  type: "docker"  # 或 "firejail"
  
  resource_limits:
    cpu: "2.0"
    memory: "1g"
    pids: 100
    
  security_options:
    no_new_privileges: true
    read_only_root: true
    drop_capabilities:
      - ALL
    add_capabilities:
      - CHOWN
      - SETGID
      - SETUID
      
  network:
    mode: "none"  # 无网络访问
    
  volumes:
    - type: "bind"
      source: "/tmp/input"
      target: "/input"
      read_only: true
    - type: "bind"
      source: "/tmp/output"
      target: "/output"
      read_only: false
    - type: "tmpfs"
      target: "/tmp"
      size: "500m"
```

---

## 3. 数据流设计

### 3.1 单文件转换流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│   API    │────▶│  Upload  │────▶│  Store   │
│  Upload  │     │ Gateway  │     │ Service  │     │  (S3)    │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────▼─────┐
│  Client  │◀────│   API    │◀────│  Celery  │◀────│  Queue   │
│  Poll    │     │ Response │     │  Worker  │     │ (Redis)  │
└──────────┘     └──────────┘     └────┬─────┘     └──────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  Converter      │
                              │  Engine         │
                              │  (Sandbox)      │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  Output Store   │
                              │  (S3)           │
                              └─────────────────┘
```

### 3.2 批量转换流程

```
┌─────────────────────────────────────────────────────────────┐
│                     Batch Conversion Flow                    │
└─────────────────────────────────────────────────────────────┘

1. Upload Phase
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
   │ File 1  │───▶│ File 2  │───▶│ File 3  │───▶│  ...    │
   └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Parallel Upload │
              │  (Streaming)     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Validation     │
              │  - Type check   │
              │  - Size check   │
              │  - Virus scan   │
              └────────┬────────┘
                       │
                       ▼
2. Queue Phase
              ┌─────────────────┐
              │  Batch Task     │
              │  Created        │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Subtask │   │ Subtask │   │ Subtask │
   │   1     │   │   2     │   │   N     │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
3. Processing Phase (Parallel Workers)
              ┌─────────────────┐
              │  Worker Pool    │
              │  (4 concurrent) │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Convert │   │ Convert │   │ Convert │
   │   1     │   │   2     │   │   N     │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
4. Completion Phase
              ┌─────────────────┐
              │  Zip Results    │
              │  (if batch)     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Notify Client  │
              │  (WebSocket)    │
              └─────────────────┘
```

---

## 4. 部署架构

### 4.1 开发环境

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "5000:5000"
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
    environment:
      - DEBUG=true
      - LOG_LEVEL=debug
      - RELOAD=true
    depends_on:
      - redis
      - postgres
      
  worker:
    build:
      context: .
      dockerfile: Dockerfile.dev
    command: celery -A tasks worker -l info -c 2
    volumes:
      - ./src:/app/src
    depends_on:
      - redis
      - postgres
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
      
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: docconverter
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: docconverter
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

### 4.2 生产环境 (Kubernetes)

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docconverter-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: docconverter-api
  template:
    metadata:
      labels:
        app: docconverter-api
    spec:
      containers:
      - name: api
        image: badhope/docformatconverter:latest
        ports:
        - containerPort: 5000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docconverter-worker
spec:
  replicas: 5
  selector:
    matchLabels:
      app: docconverter-worker
  template:
    metadata:
      labels:
        app: docconverter-worker
    spec:
      containers:
      - name: worker
        image: badhope/docformatconverter:latest
        command: ["celery", "-A", "tasks", "worker", "-l", "info", "-c", "2"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

---

## 5. 监控与可观测性

### 5.1 指标收集

```yaml
Metrics:
  application:
    - request_duration_seconds
    - request_count
    - conversion_duration_seconds
    - conversion_success_rate
    - queue_depth
    - worker_utilization
    
  system:
    - cpu_usage_percent
    - memory_usage_bytes
    - disk_usage_bytes
    - network_io_bytes
    
  business:
    - active_users
    - conversions_per_minute
    - file_size_distribution
    - format_popularity
```

### 5.2 日志结构

```json
{
  "timestamp": "2026-05-18T10:30:00Z",
  "level": "INFO",
  "service": "docconverter-api",
  "trace_id": "abc123",
  "span_id": "def456",
  "message": "Conversion completed",
  "context": {
    "task_id": "task-789",
    "user_id": "user-123",
    "source_format": "pdf",
    "target_format": "docx",
    "file_size": 1048576,
    "duration_ms": 2345
  }
}
```

### 5.3 告警规则

```yaml
Alerts:
  critical:
    - name: "HighErrorRate"
      condition: "error_rate > 5%"
      duration: "5m"
      
    - name: "QueueBacklog"
      condition: "queue_depth > 1000"
      duration: "10m"
      
  warning:
    - name: "SlowConversion"
      condition: "p95_conversion_time > 30s"
      duration: "15m"
      
    - name: "HighMemoryUsage"
      condition: "memory_usage > 80%"
      duration: "10m"
```

---

## 6. 扩展性设计

### 6.1 水平扩展策略

```
┌─────────────────────────────────────────────────────────────┐
│                    Horizontal Scaling                        │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │ Load Balancer│
                    │  (Nginx/ALB) │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  API Pod 1  │ │  API Pod 2  │ │  API Pod N  │
    │  (FastAPI)  │ │  (FastAPI)  │ │  (FastAPI)  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────┴──────┐
                    │    Redis    │
                    │   (Queue)   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ Worker Pod 1│ │ Worker Pod 2│ │ Worker Pod N│
    │  (Celery)   │ │  (Celery)   │ │  (Celery)   │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 6.2 自动扩缩容配置

```yaml
# HPA Configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: docconverter-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: docconverter-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

---

## 7. 安全架构

### 7.1 认证授权流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Client │────▶│  API    │────▶│  Auth   │────▶│  JWT    │
│         │     │ Gateway │     │ Service │     │ Service │
└─────────┘     └─────────┘     └────┬────┘     └────┬────┘
                                     │               │
                                     │               ▼
                                     │        ┌─────────┐
                                     │        │  Redis  │
                                     │        │ (Token) │
                                     │        └────┬────┘
                                     │               │
                                     └───────────────┘
                                                     │
                                                     ▼
                                              ┌─────────┐
                                              │PostgreSQL│
                                              │ (Users) │
                                              └─────────┘
```

### 7.2 数据加密

```yaml
Encryption:
  in_transit:
    protocol: "TLS 1.3"
    certificates: "Let's Encrypt / Custom"
    hsts: true
    
  at_rest:
    database: "AES-256"
    file_storage: "S3-SSE / Customer managed"
    backups: "AES-256-GCM"
    
  key_management:
    provider: "AWS KMS / HashiCorp Vault"
    rotation: "90 days"
```

---

## 8. 灾难恢复

### 8.1 备份策略

```yaml
Backup_Strategy:
  database:
    frequency: "daily"
    retention: "30 days"
    method: "pg_dump + WAL archiving"
    storage: "S3 Glacier"
    
  file_storage:
    frequency: "continuous"
    replication: "cross-region"
    versioning: "enabled"
    
  configuration:
    frequency: "on_change"
    storage: "Git + S3"
    encryption: true
```

### 8.2 恢复时间目标

| 组件 | RTO | RPO |
|------|-----|-----|
| API 服务 | 5 min | 0 |
| 转换任务 | 15 min | 0 |
| 数据库 | 30 min | 1 hour |
| 文件存储 | 1 hour | 0 |
