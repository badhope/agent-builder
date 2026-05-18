# DocFormatConverter - API 接口规范

> **版本**: 1.0.0  
> **协议**: REST + WebSocket  
> **格式**: JSON  
> **认证**: API Key / JWT  
> **基础 URL**: `https://api.docformatconverter.com/v1`

---

## 1. 接口概览

### 1.1 端点分类

| 类别 | 前缀 | 描述 | 认证 |
|------|------|------|------|
| 公共接口 | `/` | 健康检查、格式列表 | 否 |
| 转换接口 | `/convert` | 文件转换 | 可选 |
| 任务接口 | `/tasks` | 任务管理 | 是 |
| 文件接口 | `/files` | 文件管理 | 是 |
| 用户接口 | `/users` | 用户管理 | 是 |
| 管理接口 | `/admin` | 系统管理 | Admin |
| 实时接口 | `/ws` | WebSocket | 是 |

### 1.2 HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 202 | Accepted | 任务已接受，异步处理 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 认证失败 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable | 格式不支持 |
| 429 | Too Many Requests | 速率限制 |
| 500 | Internal Error | 服务器错误 |
| 503 | Service Unavailable | 服务不可用 |

### 1.3 错误响应格式

```json
{
  "error": {
    "code": "INVALID_FORMAT",
    "message": "The requested conversion format is not supported",
    "details": {
      "source_format": "xyz",
      "target_format": "abc",
      "supported_formats": ["pdf", "docx", "html"]
    },
    "request_id": "req_abc123",
    "timestamp": "2026-05-18T10:30:00Z"
  }
}
```

---

## 2. 公共接口

### 2.1 健康检查

```http
GET /health
```

**响应:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-05-18T10:30:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "storage": "connected",
    "workers": 5
  }
}
```

### 2.2 就绪检查

```http
GET /ready
```

**响应:**
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "queue": true,
    "storage": true
  }
}
```

### 2.3 支持格式列表

```http
GET /formats
```

**查询参数:**
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `category` | string | 否 | 筛选类别: document, spreadsheet, presentation, markup, data, image, ebook |
| `source` | string | 否 | 源格式，返回支持的目标格式 |

**响应:**
```json
{
  "formats": [
    {
      "category": "document",
      "source": "pdf",
      "targets": ["docx", "txt", "html", "md", "epub"],
      "metadata": {
        "max_size": "50MB",
        "supports_batch": true
      }
    },
    {
      "category": "spreadsheet",
      "source": "xlsx",
      "targets": ["csv", "pdf", "html", "json"],
      "metadata": {
        "max_size": "20MB",
        "supports_batch": true
      }
    }
  ],
  "total": 25
}
```

### 2.4 格式详情

```http
GET /formats/{source}
```

**响应:**
```json
{
  "format": "pdf",
  "category": "document",
  "mime_type": "application/pdf",
  "extensions": [".pdf"],
  "conversions": [
    {
      "target": "docx",
      "quality": "high",
      "estimated_time": "2-5s",
      "options": {
        "preserve_images": true,
        "ocr_enabled": false
      }
    }
  ],
  "limitations": {
    "max_file_size": "50MB",
    "max_pages": 1000,
    "password_protected": false
  }
}
```

---

## 3. 转换接口

### 3.1 单文件转换

```http
POST /convert
```

**请求头:**
```
Content-Type: multipart/form-data
Authorization: Bearer {token}  # 或 X-API-Key: {key}
```

**请求体:**
| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `file` | File | 是 | 要转换的文件 |
| `target_format` | string | 是 | 目标格式 |
| `options` | object | 否 | 转换选项 |
| `callback_url` | string | 否 | 回调 URL |

**Options 对象:**
```json
{
  "quality": "high",           // low, medium, high, lossless
  "preserve_metadata": true,
  "compress_output": false,
  "password": null,            // PDF 密码
  "page_range": null,          // "1-10" 或 [1, 3, 5]
  "ocr": false,                // 启用 OCR
  "ocr_language": "eng",       // OCR 语言
  "custom": {}                 // 格式特定选项
}
```

**响应 (202 Accepted):**
```json
{
  "task_id": "task_abc123",
  "status": "pending",
  "created_at": "2026-05-18T10:30:00Z",
  "estimated_duration": "5s",
  "links": {
    "self": "/tasks/task_abc123",
    "status": "/tasks/task_abc123/status",
    "result": "/tasks/task_abc123/result"
  }
}
```

### 3.2 批量转换

```http
POST /batch
```

**请求体:**
```json
{
  "files": [
    {
      "file": "<binary>",
      "target_format": "pdf",
      "options": {}
    }
  ],
  "common_options": {
    "quality": "high",
    "compress_output": true
  },
  "output_format": "zip",  // zip, individual
  "callback_url": "https://example.com/webhook"
}
```

**或使用 multipart:**
```http
Content-Type: multipart/form-data

files[]: <file1>
files[]: <file2>
target_format: pdf
output_format: zip
```

**响应 (202 Accepted):**
```json
{
  "batch_id": "batch_xyz789",
  "status": "pending",
  "total_files": 10,
  "created_at": "2026-05-18T10:30:00Z",
  "links": {
    "self": "/tasks/batch_xyz789",
    "status": "/tasks/batch_xyz789/status"
  }
}
```

### 3.3 通过 URL 转换

```http
POST /convert/url
```

**请求体:**
```json
{
  "url": "https://example.com/document.pdf",
  "target_format": "docx",
  "options": {},
  "headers": {
    "Authorization": "Bearer token"
  }
}
```

---

## 4. 任务接口

### 4.1 任务列表

```http
GET /tasks
```

**查询参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| `status` | string | 筛选状态: pending, processing, completed, failed, cancelled |
| `type` | string | 类型: single, batch |
| `from` | datetime | 开始时间 |
| `to` | datetime | 结束时间 |
| `limit` | integer | 每页数量 (默认 20, 最大 100) |
| `offset` | integer | 偏移量 |

**响应:**
```json
{
  "tasks": [
    {
      "id": "task_abc123",
      "type": "single",
      "status": "completed",
      "source_format": "pdf",
      "target_format": "docx",
      "file_name": "document.pdf",
      "file_size": 1048576,
      "created_at": "2026-05-18T10:30:00Z",
      "started_at": "2026-05-18T10:30:01Z",
      "completed_at": "2026-05-18T10:30:05Z",
      "duration_ms": 4000,
      "progress": 100
    }
  ],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

### 4.2 任务详情

```http
GET /tasks/{task_id}
```

**响应:**
```json
{
  "id": "task_abc123",
  "type": "single",
  "status": "completed",
  "source": {
    "format": "pdf",
    "file_name": "document.pdf",
    "file_size": 1048576,
    "mime_type": "application/pdf"
  },
  "target": {
    "format": "docx",
    "file_name": "document.docx",
    "file_size": 512000,
    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  },
  "options": {
    "quality": "high",
    "preserve_metadata": true
  },
  "progress": {
    "percentage": 100,
    "current_step": "completed",
    "steps": [
      {"name": "upload", "status": "completed", "duration_ms": 500},
      {"name": "validation", "status": "completed", "duration_ms": 200},
      {"name": "conversion", "status": "completed", "duration_ms": 3000},
      {"name": "packaging", "status": "completed", "duration_ms": 300}
    ]
  },
  "timestamps": {
    "created": "2026-05-18T10:30:00Z",
    "started": "2026-05-18T10:30:01Z",
    "completed": "2026-05-18T10:30:05Z"
  },
  "result": {
    "download_url": "/files/file_def456/download",
    "expires_at": "2026-05-18T11:30:00Z"
  },
  "error": null
}
```

### 4.3 批量任务详情

```http
GET /tasks/{batch_id}
```

**响应:**
```json
{
  "id": "batch_xyz789",
  "type": "batch",
  "status": "processing",
  "total_files": 10,
  "completed_files": 5,
  "failed_files": 0,
  "progress": 50,
  "files": [
    {
      "index": 1,
      "status": "completed",
      "source": "file1.pdf",
      "target": "file1.docx"
    },
    {
      "index": 2,
      "status": "processing",
      "source": "file2.pdf",
      "progress": 60
    }
  ],
  "result": null
}
```

### 4.4 取消任务

```http
DELETE /tasks/{task_id}
```

**响应 (200 OK):**
```json
{
  "id": "task_abc123",
  "status": "cancelled",
  "cancelled_at": "2026-05-18T10:30:10Z"
}
```

### 4.5 任务状态流

```
                    ┌─────────────┐
                    │   pending   │
                    │   (等待中)   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
         ┌─────────│  processing │─────────┐
         │         │   (处理中)   │         │
         │         └──────┬──────┘         │
         │                │                │
         ▼                ▼                ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │  completed  │  │   failed    │  │  cancelled  │
  │   (完成)    │  │   (失败)    │  │   (已取消)   │
  └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 5. 文件接口

### 5.1 文件列表

```http
GET /files
```

**查询参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| `task_id` | string | 关联的任务 ID |
| `format` | string | 文件格式筛选 |
| `expires_before` | datetime | 过期时间筛选 |

**响应:**
```json
{
  "files": [
    {
      "id": "file_def456",
      "task_id": "task_abc123",
      "file_name": "document.docx",
      "file_size": 512000,
      "format": "docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "created_at": "2026-05-18T10:30:05Z",
      "expires_at": "2026-05-18T11:30:05Z",
      "download_count": 0,
      "links": {
        "download": "/files/file_def456/download"
      }
    }
  ]
}
```

### 5.2 文件详情

```http
GET /files/{file_id}
```

### 5.3 下载文件

```http
GET /files/{file_id}/download
```

**响应头:**
```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="document.docx"
Content-Length: 512000
X-Expires-At: 2026-05-18T11:30:05Z
```

### 5.4 删除文件

```http
DELETE /files/{file_id}
```

---

## 6. 用户接口

### 6.1 获取当前用户

```http
GET /users/me
```

**响应:**
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "plan": "free",
  "quota": {
    "conversions_per_day": 100,
    "conversions_used_today": 25,
    "storage_mb": 1000,
    "storage_used_mb": 250,
    "max_file_size_mb": 50
  },
  "api_keys": [
    {
      "id": "key_abc",
      "name": "Production",
      "prefix": "dfc_pk_",
      "created_at": "2026-01-01T00:00:00Z",
      "last_used_at": "2026-05-18T10:00:00Z"
    }
  ],
  "created_at": "2026-01-01T00:00:00Z"
}
```

### 6.2 创建 API Key

```http
POST /users/me/api-keys
```

**请求体:**
```json
{
  "name": "Development"
}
```

**响应 (201 Created):**
```json
{
  "id": "key_xyz",
  "name": "Development",
  "key": "dfc_pk_live_abc123xyz789",  // 只显示一次
  "prefix": "dfc_pk_",
  "created_at": "2026-05-18T10:30:00Z"
}
```

### 6.3 删除 API Key

```http
DELETE /users/me/api-keys/{key_id}
```

### 6.4 使用统计

```http
GET /users/me/stats
```

**查询参数:**
| 参数 | 类型 | 描述 |
|------|------|------|
| `period` | string | 统计周期: day, week, month, year |
| `from` | date | 开始日期 |
| `to` | date | 结束日期 |

**响应:**
```json
{
  "period": "month",
  "from": "2026-04-01",
  "to": "2026-04-30",
  "total_conversions": 1500,
  "total_files_processed": 3000,
  "total_bytes_in": 1572864000,
  "total_bytes_out": 524288000,
  "success_rate": 0.98,
  "average_duration_ms": 3500,
  "by_format": {
    "pdf_to_docx": 500,
    "xlsx_to_csv": 400,
    "md_to_html": 300
  }
}
```

---

## 7. WebSocket 实时接口

### 7.1 连接

```
wss://api.docformatconverter.com/v1/ws
```

**连接参数:**
```
?token={jwt_token}
```

### 7.2 消息类型

#### 7.2.1 订阅任务更新

**Client → Server:**
```json
{
  "type": "subscribe",
  "task_ids": ["task_abc123", "task_def456"]
}
```

**Server → Client:**
```json
{
  "type": "subscribed",
  "task_ids": ["task_abc123", "task_def456"]
}
```

#### 7.2.2 任务进度更新

**Server → Client:**
```json
{
  "type": "progress",
  "task_id": "task_abc123",
  "data": {
    "status": "processing",
    "progress": 65,
    "current_step": "conversion",
    "message": "Converting page 65 of 100"
  },
  "timestamp": "2026-05-18T10:30:03Z"
}
```

#### 7.2.3 任务完成通知

**Server → Client:**
```json
{
  "type": "completed",
  "task_id": "task_abc123",
  "data": {
    "status": "completed",
    "result": {
      "download_url": "/files/file_def456/download",
      "file_size": 512000
    },
    "duration_ms": 5000
  },
  "timestamp": "2026-05-18T10:30:05Z"
}
```

#### 7.2.4 错误通知

**Server → Client:**
```json
{
  "type": "error",
  "task_id": "task_abc123",
  "data": {
    "code": "CONVERSION_FAILED",
    "message": "Failed to convert PDF: corrupted file",
    "retryable": false
  },
  "timestamp": "2026-05-18T10:30:05Z"
}
```

### 7.3 心跳机制

**Client → Server (每 30 秒):**
```json
{
  "type": "ping",
  "timestamp": "2026-05-18T10:30:00Z"
}
```

**Server → Client:**
```json
{
  "type": "pong",
  "timestamp": "2026-05-18T10:30:00Z"
}
```

---

## 8. Webhook

### 8.1 配置 Webhook

在用户设置中配置回调 URL。

### 8.2 Webhook 事件

#### 8.2.1 任务完成

```json
{
  "event": "task.completed",
  "timestamp": "2026-05-18T10:30:05Z",
  "data": {
    "task_id": "task_abc123",
    "user_id": "user_123",
    "status": "completed",
    "source_format": "pdf",
    "target_format": "docx",
    "result": {
      "download_url": "https://api.docformatconverter.com/v1/files/file_def456/download?token=xxx",
      "expires_at": "2026-05-18T11:30:05Z"
    }
  }
}
```

#### 8.2.2 任务失败

```json
{
  "event": "task.failed",
  "timestamp": "2026-05-18T10:30:05Z",
  "data": {
    "task_id": "task_abc123",
    "user_id": "user_123",
    "status": "failed",
    "error": {
      "code": "INVALID_FILE",
      "message": "The uploaded file is corrupted"
    }
  }
}
```

### 8.3 Webhook 签名验证

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 9. 速率限制

### 9.1 限制规则

| 端点 | 限制 | 窗口 |
|------|------|------|
| `/convert` | 10 | 1 minute |
| `/batch` | 5 | 1 minute |
| `/tasks` | 100 | 1 minute |
| `/files` | 100 | 1 minute |
| `/formats` | 1000 | 1 minute |
| WebSocket | 1 | 1 connection |

### 9.2 响应头

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1716031800
X-RateLimit-Retry-After: 60
```

### 9.3 超出限制响应

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "retry_after": 60
  }
}
```

---

## 10. SDK 示例

### 10.1 Python SDK

```python
from docformatconverter import Client

# 初始化客户端
client = Client(api_key="your_api_key")

# 单文件转换
with open("document.pdf", "rb") as f:
    task = client.convert(
        file=f,
        target_format="docx",
        options={"quality": "high"}
    )

# 等待完成
result = task.wait()
print(f"Download: {result.download_url}")

# 批量转换
files = [
    ("file1.pdf", "docx"),
    ("file2.xlsx", "csv"),
]
tasks = client.batch_convert(files)

# 使用 WebSocket 实时更新
@client.on_progress
def on_progress(task_id, progress):
    print(f"{task_id}: {progress}%")

client.connect_websocket()
```

### 10.2 JavaScript SDK

```javascript
import { DocFormatConverter } from '@docformatconverter/sdk';

const client = new DocFormatConverter({ apiKey: 'your_api_key' });

// 单文件转换
const task = await client.convert({
  file: fileInput.files[0],
  targetFormat: 'docx',
  options: { quality: 'high' }
});

// 监听进度
task.onProgress((progress) => {
  console.log(`${progress.percentage}%`);
});

const result = await task.wait();
console.log(result.downloadUrl);

// 批量转换
const batch = await client.batchConvert({
  files: [file1, file2, file3],
  targetFormat: 'pdf'
});

batch.onFileComplete((file, index) => {
  console.log(`File ${index} completed`);
});
```

### 10.3 cURL 示例

```bash
# 单文件转换
curl -X POST https://api.docformatconverter.com/v1/convert \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf" \
  -F "target_format=docx" \
  -F "options={\"quality\":\"high\"}"

# 查询任务状态
curl https://api.docformatconverter.com/v1/tasks/task_abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 下载结果
curl https://api.docformatconverter.com/v1/files/file_def456/download \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o converted.docx
```

---

## 11. 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-18 | 初始 API 设计 |
