# 🔄 DocFormatConverter

<p align="center">
  <strong>轻量级多格式批量文档转换器</strong><br>
  在线轻松转换 PDF、DOCX、XLSX、PPTX、Markdown、HTML、CSV、TXT、JSON、XML、YAML、EPUB 等多种格式。
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#支持格式">支持格式</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#api">API</a> •
  <a href="#参与贡献">参与贡献</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/版本-1.0.0-blue.svg" alt="版本">
  <img src="https://img.shields.io/badge/许可证-MIT-green.svg" alt="许可证">
  <img src="https://img.shields.io/badge/python-3.12+-yellow.svg" alt="Python">
</p>

---

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 🚀 **快速轻量** | 最少的依赖，最大的性能 |
| 📦 **批量处理** | 一次性转换数百个文件 |
| 🔒 **隐私优先** | 所有处理在本地完成 |
| 🌐 **网页界面** | 简洁、响应式的用户界面 |
| 🔌 **REST API** | 完整的 API，支持编程访问 |
| 📱 **响应式设计** | 在桌面端、平板和手机上都能完美运行 |

---

## 📁 支持格式

### 文档
PDF, DOCX, DOC, ODT, RTF, EPUB, MOBI

### 电子表格
XLSX, XLS, CSV, TSV, ODS

### 演示文稿
PPTX, PPT, ODP

### 标记与数据
Markdown, HTML, JSON, XML, YAML, TXT

### 图像
PNG, JPG, WEBP, BMP, TIFF, SVG

---

## 🚀 快速开始

### Docker 部署（推荐）

```bash
docker pull badhope/docformatconverter:latest
docker run -d -p 5000:5000 --name doc-converter badhope/docformatconverter:latest
```

### 手动安装

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
pip install -r requirements.txt
python app.py
```

网页界面：**http://localhost:5000**

---

## 🔌 API

### 转换单个文件

```bash
curl -X POST http://localhost:5000/api/convert \
  -F "file=@document.pdf" \
  -F "target_format=docx" \
  -o converted.docx
```

### 批量转换

```bash
curl -X POST http://localhost:5000/api/batch \
  -F "files=@file1.pdf" \
  -F "files=@file2.docx" \
  -F "target_format=pdf" \
  -o results.zip
```

---

## 📖 文档

- [设计规范](spec/design.md)
- [技术架构](spec/architecture.md)
- [API 参考](spec/api.md)
- [数据库设计](spec/database.md)
- [UI/UX 设计](spec/ui-design.md)
- [开发任务](spec/tasks.md)

---

## 🤝 参与贡献

欢迎贡献！请阅读 [贡献指南](CONTRIBUTING.md)。

---

## 📄 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)。

---

<p align="center">
  由 <a href="https://github.com/badhope">badhope</a> 用 ❤️ 制作
</p>
