# 🔄 DocFormatConverter

<p align="center">
  <strong>Lightweight Multi-Format Batch Document Converter</strong><br>
  Convert PDF, DOCX, XLSX, PPTX, Markdown, HTML, CSV, TXT, JSON, XML, YAML, EPUB, and more — online with ease.
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#supported-formats">Formats</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api">API</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/python-3.12+-yellow.svg" alt="Python">
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **Fast & Lightweight** | Minimal dependencies, maximum performance |
| 📦 **Batch Processing** | Convert hundreds of files in one go |
| 🔒 **Privacy First** | All processing happens locally |
| 🌐 **Web Interface** | Clean, responsive UI |
| 🔌 **REST API** | Full API for programmatic access |
| 📱 **Responsive Design** | Works on desktop, tablet, and mobile |

---

## 📁 Supported Formats

### Documents
PDF, DOCX, DOC, ODT, RTF, EPUB, MOBI

### Spreadsheets
XLSX, XLS, CSV, TSV, ODS

### Presentations
PPTX, PPT, ODP

### Markup & Data
Markdown, HTML, JSON, XML, YAML, TXT

### Images
PNG, JPG, WEBP, BMP, TIFF, SVG

---

## 🚀 Quick Start

### Docker (Recommended)

```bash
docker pull badhope/docformatconverter:latest
docker run -d -p 5000:5000 --name doc-converter badhope/docformatconverter:latest
```

### Manual Installation

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
pip install -r requirements.txt
python app.py
```

Web interface: **http://localhost:5000**

---

## 🔌 API

### Convert a file

```bash
curl -X POST http://localhost:5000/api/convert \
  -F "file=@document.pdf" \
  -F "target_format=docx" \
  -o converted.docx
```

### Batch conversion

```bash
curl -X POST http://localhost:5000/api/batch \
  -F "files=@file1.pdf" \
  -F "files=@file2.docx" \
  -F "target_format=pdf" \
  -o results.zip
```

---

## 📖 Documentation

- [Design Specification](spec/design.md)
- [Architecture](spec/architecture.md)
- [API Reference](spec/api.md)
- [Database Schema](spec/database.md)
- [UI/UX Design](spec/ui-design.md)
- [Development Tasks](spec/tasks.md)

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md).

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/badhope">badhope</a>
</p>
