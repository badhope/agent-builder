# DocFormatConverter - 项目设计规范

> **版本**: 1.0.0  
> **日期**: 2026-05-18  
> **状态**: 设计阶段  
> **作者**: badhope

---

## 1. 项目概述

### 1.1 项目定位
**DocFormatConverter** 是一个轻量级、开源的在线多格式文档批量转换工具，定位为开发者友好的文档处理基础设施。

### 1.2 核心价值主张
- **极速体验**: 毫秒级响应，秒级转换
- **隐私优先**: 本地处理，数据不出境
- **批量能力**: 支持数百文件同时处理
- **无缝集成**: 完整的 REST API + WebSocket 实时反馈

### 1.3 目标用户
| 用户类型 | 使用场景 | 核心需求 |
|---------|---------|---------|
| 开发者 | 集成文档转换功能到应用 | API稳定性、SDK支持 |
| 内容创作者 | 批量转换文档格式 | 易用性、格式兼容性 |
| 企业用户 | 内部文档处理工作流 | 安全性、可扩展性 |
| 普通用户 | 偶尔的文件转换 | 零配置、即开即用 |

---

## 2. 功能规格

### 2.1 核心功能矩阵

```
┌─────────────────────────────────────────────────────────────────┐
│                    功能架构图                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │   Web UI    │    │   REST API  │    │  WebSocket  │        │
│   │  (React)    │    │  (FastAPI)  │    │  (实时推送)  │        │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│          │                  │                  │               │
│          └──────────────────┼──────────────────┘               │
│                             │                                  │
│                    ┌────────┴────────┐                        │
│                    │  核心转换引擎    │                        │
│                    │  (Converter     │                        │
│                    │   Engine)       │                        │
│                    └────────┬────────┘                        │
│                             │                                  │
│          ┌──────────────────┼──────────────────┐              │
│          │                  │                  │               │
│   ┌──────┴──────┐    ┌──────┴──────┐    ┌──────┴──────┐       │
│   │  文档转换   │    │  表格转换   │    │  演示转换   │       │
│   │  (Libre)   │    │  (OpenPyXL) │    │  (python-   │       │
│   │            │    │            │    │   pptx)     │       │
│   └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│   │  标记语言   │    │  数据格式   │    │  图像处理   │       │
│   │  (Pandoc)  │    │  (原生)     │    │  (Pillow)   │       │
│   └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 支持的格式详细规格

#### 2.2.1 文档格式支持表

| 源格式 | 目标格式 | 转换引擎 | 质量等级 | 备注 |
|--------|---------|---------|---------|------|
| PDF | DOCX, TXT, HTML, MD, EPUB | pdfplumber + python-docx | ⭐⭐⭐⭐⭐ | 保留布局 |
| PDF | PNG/JPG (每页) | pdf2image | ⭐⭐⭐⭐⭐ | 300 DPI |
| DOCX | PDF, HTML, TXT, MD, EPUB | python-docx + pypandoc | ⭐⭐⭐⭐⭐ | 完整样式 |
| DOCX | ODT | LibreOffice | ⭐⭐⭐⭐⭐ | 原生转换 |
| ODT | DOCX, PDF | LibreOffice | ⭐⭐⭐⭐⭐ | 原生转换 |
| RTF | DOCX, PDF, TXT | pypandoc | ⭐⭐⭐⭐ | 基础支持 |
| EPUB | PDF, TXT, HTML, MD | ebooklib + pypandoc | ⭐⭐⭐⭐ | 保留元数据 |
| MOBI | EPUB, PDF, TXT | Calibre (可选) | ⭐⭐⭐ | 需额外安装 |

#### 2.2.2 电子表格格式支持表

| 源格式 | 目标格式 | 转换引擎 | 特性支持 |
|--------|---------|---------|---------|
| XLSX | CSV, TSV, JSON, HTML, PDF | openpyxl | 公式、样式、图表 |
| XLSX | ODS | openpyxl | 完整兼容 |
| XLS | XLSX, CSV, PDF | xlrd + openpyxl | 旧格式兼容 |
| CSV | XLSX, JSON, TSV, HTML | pandas | 自动类型检测 |
| ODS | XLSX, CSV, PDF | odfpy | OpenDocument |

#### 2.2.3 演示文稿格式支持表

| 源格式 | 目标格式 | 转换引擎 | 特性支持 |
|--------|---------|---------|---------|
| PPTX | PDF, HTML, PNG (每页) | python-pptx | 动画、过渡效果 |
| PPTX | ODP | python-pptx | 标准兼容 |
| PPT | PPTX, PDF | LibreOffice | 旧格式兼容 |
| ODP | PPTX, PDF | LibreOffice | OpenDocument |

#### 2.2.4 标记与数据格式支持表

| 源格式 | 目标格式 | 转换引擎 | 特性 |
|--------|---------|---------|------|
| Markdown | HTML, PDF, DOCX | pypandoc + WeasyPrint | GFM, 数学公式 |
| HTML | PDF, Markdown, TXT | WeasyPrint + BeautifulSoup | CSS 样式保留 |
| JSON | CSV, XML, YAML, XLSX | 原生 Python | 嵌套展开 |
| XML | JSON, CSV, YAML | xmltodict + lxml | Schema 验证 |
| YAML | JSON, XML | PyYAML | 注释保留选项 |
| CSV | JSON, XML, YAML, XLSX | pandas | 大文件流式处理 |

#### 2.2.5 图像格式支持表

| 源格式 | 目标格式 | 转换引擎 | 特性 |
|--------|---------|---------|------|
| PNG | JPG, WEBP, PDF, BMP, TIFF | Pillow | 透明度处理 |
| JPG | PNG, WEBP, PDF, BMP | Pillow | 质量可调 |
| WEBP | PNG, JPG, GIF | Pillow | 动画帧提取 |
| HEIC/HEIF | JPG, PNG | pillow-heif | iOS 照片支持 |
| SVG | PNG, JPG, PDF, WEBP | CairoSVG | 矢量渲染 |
| TIFF | PNG, JPG, PDF | Pillow | 多页支持 |

### 2.3 批量处理规格

```yaml
BatchProcessing:
  max_files_per_batch: 100
  max_total_size: 500MB
  supported_modes:
    - single_format: "所有文件转为同一格式"
    - mixed_format: "根据源格式智能选择目标格式"
    - template_based: "基于命名模板的批量转换"
  
  queue_management:
    strategy: "优先级队列 + 公平调度"
    max_concurrent: 4
    timeout_per_file: 300s
    retry_policy:
      max_retries: 3
      backoff: "exponential"
  
  progress_tracking:
    websocket: true
    sse: true
    polling: true
    granularity: "per_file"
```

---

## 3. 非功能需求

### 3.1 性能指标

| 指标 | 目标值 | 测试方法 |
|------|--------|---------|
| 单文件转换 (1MB PDF→DOCX) | < 3s | 平均10次测试 |
| 批量转换 (10文件) | < 15s | 并行处理 |
| API 响应时间 (P99) | < 100ms | 负载测试 |
| 并发用户数 | 100+ | 压力测试 |
| 内存占用 (空闲) | < 200MB | 监控 |
| 内存占用 (峰值) | < 2GB | 大文件测试 |

### 3.2 安全要求

```yaml
Security:
  input_validation:
    file_type: "魔数检测 + 扩展名双重验证"
    file_size: "可配置上限，默认50MB"
    content_scan: "可选病毒扫描集成"
  
  sandbox:
    enabled: true
    method: "Docker容器 / Firejail"
    resource_limits:
      cpu: "2 cores"
      memory: "1GB"
      timeout: "300s"
  
  data_protection:
    encryption_at_rest: "可选 AES-256"
    auto_cleanup: "24小时后自动删除"
    audit_log: "所有操作记录"
  
  api_security:
    authentication: "API Key / JWT"
    rate_limiting: "100 req/min per key"
    cors: "可配置白名单"
```

### 3.3 可用性要求

- **SLA**: 99.9% 可用性
- **故障恢复**: 自动重启，状态持久化
- **监控**: Prometheus + Grafana 集成
- **日志**: 结构化日志，ELK 兼容

---

## 4. 技术约束

### 4.1 技术栈约束

```
后端:
  - Python 3.12+ (主语言)
  - FastAPI (Web框架)
  - Celery (任务队列)
  - Redis (缓存/消息)
  - PostgreSQL (元数据存储)
  
前端:
  - React 18+ (UI框架)
  - TypeScript (类型安全)
  - Tailwind CSS (样式)
  - Vite (构建工具)
  
部署:
  - Docker (容器化)
  - Docker Compose (本地)
  - Kubernetes (生产)
```

### 4.2 外部依赖

| 依赖 | 用途 | 许可 | 必需 |
|------|------|------|------|
| LibreOffice | 文档转换 | MPL-2.0 | 是 |
| Pandoc | 标记语言转换 | GPL-2.0+ | 是 |
| WeasyPrint | HTML→PDF | BSD-3 | 是 |
| Calibre | 电子书转换 | GPL-3.0 | 可选 |

---

## 5. 用户旅程

### 5.1 Web UI 用户旅程

```
[访问首页] → [拖拽上传] → [选择格式] → [调整选项] → [开始转换] → [下载结果]
    ↓           ↓           ↓           ↓           ↓           ↓
  展示支持    实时验证    智能推荐    质量/压缩    进度条      批量下载
  的格式      文件类型    目标格式    设置        实时更新    ZIP/单独
```

### 5.2 API 用户旅程

```
[获取API Key] → [上传文件] → [创建任务] → [轮询状态] → [下载结果]
     ↓            ↓           ↓           ↓           ↓
   注册/登录    预签名URL   异步处理    WebHook     临时链接
                              回调      (可选)
```

---

## 6. 成功标准

### 6.1 技术指标
- [ ] 单文件转换成功率 > 99%
- [ ] 批量转换成功率 > 95%
- [ ] API 可用性 > 99.9%
- [ ] 平均响应时间 < 100ms

### 6.2 用户指标
- [ ] 首次转换完成时间 < 2分钟
- [ ] 用户满意度 > 4.5/5
- [ ] 文档覆盖率 > 90%
- [ ] 社区贡献者 > 10人

---

## 7. 风险与缓解

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|---------|
| 大文件导致内存溢出 | 高 | 中 | 流式处理 + 分块转换 |
| 恶意文件上传 | 高 | 中 | 沙箱 + 病毒扫描 |
| 格式转换质量差 | 中 | 高 | 多引擎 fallback |
| 依赖库许可冲突 | 中 | 低 | 许可审计 + 替代方案 |

---

## 8. 附录

### 8.1 术语表
- **OCR**: 光学字符识别
- **Sandbox**: 沙箱环境
- **Webhook**: HTTP 回调
- **Streaming**: 流式处理

### 8.2 参考文档
- [LibreOffice API](https://api.libreoffice.org/)
- [Pandoc Manual](https://pandoc.org/manual.html)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

### 8.3 变更历史
| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| 1.0.0 | 2026-05-18 | 初始设计 | badhope |
