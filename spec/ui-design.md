# DocFormatConverter - UI/UX 设计规范

> **版本**: 1.0.0  
> **设计系统**: Modern Minimalist  
> **色彩模式**: Light/Dark 双主题  
> **响应式**: Mobile First

---

## 1. 设计原则

### 1.1 核心原则

```
┌─────────────────────────────────────────────────────────────────┐
│                     Design Principles                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. CLARITY    清晰                                            │
│      用户3秒内理解如何操作                                       │
│                                                                 │
│   2. EFFICIENCY 高效                                            │
│      最少点击完成核心任务                                        │
│                                                                 │
│   3. FEEDBACK   反馈                                            │
│      每个操作都有即时响应                                        │
│                                                                 │
│   4. TRUST      信任                                            │
│      隐私优先，数据安全可见                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 用户画像

| 类型 | 特征 | 使用场景 | 设计重点 |
|------|------|---------|---------|
| **快速用户** | 偶尔使用 | 快速转换单个文件 | 拖拽即转，零配置 |
| **专业用户** | 高频使用 | 批量处理，精细控制 | 高级选项，批量操作 |
| **开发者** | 技术背景 | API集成，自动化 | 文档清晰，SDK友好 |

---

## 2. 色彩系统

### 2.1 主色调

```css
/* Primary Colors */
--color-primary-50:  #EEF2FF;
--color-primary-100: #E0E7FF;
--color-primary-200: #C7D2FE;
--color-primary-300: #A5B4FC;
--color-primary-400: #818CF8;
--color-primary-500: #6366F1;  /* 主色 */
--color-primary-600: #4F46E5;
--color-primary-700: #4338CA;
--color-primary-800: #3730A3;
--color-primary-900: #312E81;

/* Secondary Colors */
--color-secondary-500: #10B981;  /* 成功 */
--color-warning-500: #F59E0B;    /* 警告 */
--color-error-500: #EF4444;      /* 错误 */
--color-info-500: #3B82F6;       /* 信息 */
```

### 2.2 亮色主题

```css
/* Light Theme */
--bg-primary: #FFFFFF;
--bg-secondary: #F9FAFB;
--bg-tertiary: #F3F4F6;
--bg-elevated: #FFFFFF;

--text-primary: #111827;
--text-secondary: #4B5563;
--text-tertiary: #9CA3AF;
--text-inverse: #FFFFFF;

--border-primary: #E5E7EB;
--border-secondary: #D1D5DB;

--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
```

### 2.3 暗色主题

```css
/* Dark Theme */
--bg-primary: #0F172A;
--bg-secondary: #1E293B;
--bg-tertiary: #334155;
--bg-elevated: #1E293B;

--text-primary: #F8FAFC;
--text-secondary: #CBD5E1;
--text-tertiary: #64748B;
--text-inverse: #0F172A;

--border-primary: #334155;
--border-secondary: #475569;

--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
```

### 2.4 语义化颜色

| 用途 | 亮色 | 暗色 |
|------|------|------|
| 成功 | `#10B981` | `#34D399` |
| 警告 | `#F59E0B` | `#FBBF24` |
| 错误 | `#EF4444` | `#F87171` |
| 信息 | `#3B82F6` | `#60A5FA` |
| 进行中 | `#6366F1` | `#818CF8` |

---

## 3. 排版系统

### 3.1 字体栈

```css
/* Font Family */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;

/* Font Loading */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

### 3.2 字号规范

| 级别 | 大小 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| Display | 48px | 700 | 1.1 | Hero 标题 |
| H1 | 36px | 700 | 1.2 | 页面标题 |
| H2 | 30px | 600 | 1.3 | 区块标题 |
| H3 | 24px | 600 | 1.4 | 卡片标题 |
| H4 | 20px | 600 | 1.4 | 小标题 |
| H5 | 18px | 500 | 1.5 | 列表标题 |
| Body Large | 18px | 400 | 1.6 | 重要正文 |
| Body | 16px | 400 | 1.6 | 默认正文 |
| Body Small | 14px | 400 | 1.5 | 次要文字 |
| Caption | 12px | 500 | 1.4 | 标签、注释 |
| Overline | 12px | 600 | 1.2 | 大写标签 |

### 3.3 响应式排版

```css
/* Mobile First */
@media (max-width: 640px) {
  --text-display: 32px;
  --text-h1: 28px;
  --text-h2: 24px;
  --text-h3: 20px;
}

@media (min-width: 1024px) {
  --text-display: 48px;
  --text-h1: 36px;
  --text-h2: 30px;
  --text-h3: 24px;
}
```

---

## 4. 间距系统

### 4.1 间距刻度

```css
/* Spacing Scale (4px base) */
--space-0: 0;
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
--space-20: 80px;
--space-24: 96px;
```

### 4.2 布局间距

| 元素 | 间距 |
|------|------|
| 页面内边距 | 24px (mobile) / 48px (desktop) |
| 卡片内边距 | 24px |
| 表单字段间距 | 16px |
| 按钮组间距 | 12px |
| 列表项间距 | 8px |

---

## 5. 组件规范

### 5.1 按钮

#### 主按钮 (Primary)

```
┌─────────────────────────────────────┐
│  [Icon]  Button Text                │
│  bg: primary-500                    │
│  text: white                        │
│  padding: 12px 24px                 │
│  border-radius: 8px                 │
│  font-weight: 500                   │
│  hover: primary-600                 │
│  active: primary-700                │
│  disabled: opacity 0.5              │
└─────────────────────────────────────┘
```

#### 次要按钮 (Secondary)

```
┌─────────────────────────────────────┐
│  [Icon]  Button Text                │
│  bg: transparent                    │
│  border: 1px solid border-primary   │
│  text: text-primary                 │
│  hover: bg-secondary                │
└─────────────────────────────────────┘
```

#### 幽灵按钮 (Ghost)

```
┌─────────────────────────────────────┐
│  [Icon]  Button Text                │
│  bg: transparent                    │
│  text: primary-500                  │
│  hover: primary-50                  │
└─────────────────────────────────────┘
```

### 5.2 输入框

```
┌─────────────────────────────────────┐
│  Label                              │
│  ┌─────────────────────────────┐    │
│  │ [Icon] Placeholder...    [X]│    │
│  │ border: 1px                 │    │
│  │ border-radius: 8px          │    │
│  │ padding: 12px 16px          │    │
│  │ focus: primary-500 ring     │    │
│  │ error: error-500 border     │    │
│  └─────────────────────────────┘    │
│  Helper text / Error message          │
└─────────────────────────────────────┘
```

### 5.3 卡片

```
┌─────────────────────────────────────┐
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │      Card Content           │    │
│  │                             │    │
│  │  bg: bg-elevated            │    │
│  │  border-radius: 12px        │    │
│  │  shadow: shadow-md          │    │
│  │  padding: 24px              │    │
│  │                             │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### 5.4 上传区域

```
┌─────────────────────────────────────┐
│                                     │
│           ┌─────────┐               │
│           │   📤    │               │
│           └─────────┘               │
│                                     │
│    Drag & drop files here           │
│    or click to browse               │
│                                     │
│    Supports: PDF, DOCX, XLSX...     │
│                                     │
│  border: 2px dashed border-primary  │
│  border-radius: 16px                │
│  hover: primary-100 bg              │
│  active: primary-200 bg             │
│                                     │
└─────────────────────────────────────┘
```

### 5.5 进度条

```
┌─────────────────────────────────────┐
│  Converting... 65%                  │
│  ┌─────────────────────────────┐    │
│  │████████████████████░░░░░░░░░│    │
│  │ height: 8px                 │    │
│  │ border-radius: 4px          │    │
│  │ bg: bg-tertiary             │    │
│  │ fill: primary-500           │    │
│  └─────────────────────────────┘    │
│  Processing page 65 of 100          │
└─────────────────────────────────────┘
```

### 5.6 文件列表项

```
┌─────────────────────────────────────┐
│  ┌────┐  document.pdf              │
│  │ 📄 │  2.5 MB  •  PDF            │
│  └────┘                             │
│         ┌─────────────────────┐     │
│         │████████████████░░░░░│     │
│         └─────────────────────┘     │
│  [Remove]              [Status]     │
│                                     │
│  padding: 16px                      │
│  border-bottom: 1px border-primary  │
└─────────────────────────────────────┘
```

---

## 6. 页面布局

### 6.1 首页布局

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo]    Home  Features  API  Docs    [Theme] [Sign In]   │  Header
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              Convert Any Document Format                    │  Hero
│         Fast, secure, and free online converter             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │  Upload
│  │              [   DRAG & DROP ZONE   ]               │   │  Zone
│  │                                                     │   │
│  │         Drop files here or click to upload          │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │  Features
│  │    ⚡️      │  │    🔒      │  │    📦      │        │
│  │    Fast     │  │   Secure   │  │   Batch    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Supported Formats                                          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐         │
│  │ PDF │ │DOCX │ │XLSX │ │PPTX │ │ MD  │ │HTML │         │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘         │
├─────────────────────────────────────────────────────────────┤
│  © 2026 DocFormatConverter  [GitHub] [Twitter] [Discord]   │  Footer
└─────────────────────────────────────────────────────────────┘
```

### 6.2 转换页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo]                                    [Theme] [User ▼] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. Upload Files                                    │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │     [DRAG & DROP OR CLICK TO UPLOAD]        │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  │                                                     │   │
│  │  2. Select Format                                   │   │
│  │  ┌─────────────┐    ┌─────────────────────────┐   │   │
│  │  │ PDF ▼      │ →  │ DOCX ▼                 │   │   │
│  │  └─────────────┘    └─────────────────────────┘   │   │
│  │                                                     │   │
│  │  3. Options [Advanced ▼]                           │   │
│  │  ☑ Preserve metadata  ☑ Compress output            │   │
│  │                                                     │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │         [    CONVERT NOW    ]               │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Recent Conversions                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📄 document.pdf → document.docx  ✓ 2 mins ago     │   │
│  │ 📊 data.xlsx → data.csv  ✓ 5 mins ago             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 响应式断点

```css
/* Breakpoints */
--breakpoint-sm: 640px;   /* Mobile landscape */
--breakpoint-md: 768px;   /* Tablet */
--breakpoint-lg: 1024px;  /* Desktop */
--breakpoint-xl: 1280px;  /* Large desktop */
--breakpoint-2xl: 1536px; /* Extra large */

/* Container */
.container {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 16px;
}

@media (min-width: 640px) {
  .container { padding: 0 24px; }
}

@media (min-width: 1024px) {
  .container { padding: 0 48px; }
}
```

---

## 7. 动效规范

### 7.1 过渡动画

```css
/* Duration */
--duration-instant: 0ms;
--duration-fast: 150ms;
--duration-normal: 250ms;
--duration-slow: 350ms;
--duration-slower: 500ms;

/* Easing */
--ease-linear: linear;
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
```

### 7.2 常用动画

| 动画 | 时长 | 缓动 | 用途 |
|------|------|------|------|
| Fade In | 250ms | ease-out | 页面加载 |
| Slide Up | 350ms | ease-out | 模态框 |
| Scale | 200ms | ease-bounce | 按钮点击 |
| Progress | 300ms | linear | 进度条 |
| Spinner | 1s | linear infinite | 加载中 |

### 7.3 动画示例

```css
/* Button Hover */
.btn {
  transition: all 250ms var(--ease-out);
}
.btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
.btn:active {
  transform: translateY(0);
}

/* Card Hover */
.card {
  transition: transform 300ms var(--ease-out),
              box-shadow 300ms var(--ease-out);
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
}

/* Upload Zone Drag Over */
.upload-zone {
  transition: all 250ms var(--ease-out);
}
.upload-zone.drag-over {
  background: var(--color-primary-50);
  border-color: var(--color-primary-500);
  transform: scale(1.02);
}

/* Progress Bar */
@keyframes progress-stripes {
  from { background-position: 1rem 0; }
  to { background-position: 0 0; }
}
.progress-bar-animated {
  animation: progress-stripes 1s linear infinite;
  background-image: linear-gradient(
    45deg,
    rgba(255,255,255,.15) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255,255,255,.15) 50%,
    rgba(255,255,255,.15) 75%,
    transparent 75%,
    transparent
  );
  background-size: 1rem 1rem;
}
```

---

## 8. 图标系统

### 8.1 图标库

使用 **Lucide React** 图标库：

```bash
npm install lucide-react
```

### 8.2 常用图标

| 用途 | 图标名 | 示例 |
|------|--------|------|
| 上传 | Upload | `<Upload />` |
| 下载 | Download | `<Download />` |
| 文件 | FileText | `<FileText />` |
| 成功 | CheckCircle | `<CheckCircle />` |
| 错误 | XCircle | `<XCircle />` |
| 警告 | AlertTriangle | `<AlertTriangle />` |
| 加载 | Loader2 | `<Loader2 className="animate-spin" />` |
| 设置 | Settings | `<Settings />` |
| 主题 | Sun / Moon | `<Sun />` / `<Moon />` |

### 8.3 图标尺寸

```css
--icon-xs: 12px;
--icon-sm: 16px;
--icon-md: 20px;
--icon-lg: 24px;
--icon-xl: 32px;
--icon-2xl: 48px;
```

---

## 9. 交互模式

### 9.1 文件上传流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Select    │───▶│   Upload    │───▶│   Convert   │───▶│   Download  │
│   Files     │    │   (0-100%)  │    │   (0-100%)  │    │   Ready     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
  [File List]       [Progress]        [Progress]          [Success]
  Validation        Uploading         Converting          Preview
```

### 9.2 错误处理

```
┌─────────────────────────────────────┐
│  ⚠️  Conversion Failed              │
│                                     │
│  Unable to convert file.pdf         │
│  The file appears to be corrupted.  │
│                                     │
│  [Try Again]  [Contact Support]     │
│                                     │
│  Error Code: FILE_CORRUPTED_001     │
└─────────────────────────────────────┘
```

### 9.3 空状态

```
┌─────────────────────────────────────┐
│                                     │
│           📭                        │
│                                     │
│    No conversions yet               │
│                                     │
│    Upload your first file to get    │
│    started                          │
│                                     │
│    [Upload File]                    │
│                                     │
└─────────────────────────────────────┘
```

---

## 10. 无障碍设计

### 10.1 色彩对比度

- 正文文字与背景对比度 ≥ 4.5:1
- 大文字与背景对比度 ≥ 3:1
- 交互元素对比度 ≥ 3:1

### 10.2 键盘导航

- 所有交互元素可通过 Tab 键访问
- 焦点状态清晰可见 (focus ring)
- 支持 Enter/Space 激活
- 模态框支持 Escape 关闭

### 10.3 屏幕阅读器

```html
<!-- 按钮带图标 -->
<button aria-label="Upload file">
  <Upload aria-hidden="true" />
</button>

<!-- 进度条 -->
<div role="progressbar" 
     aria-valuenow="65" 
     aria-valuemin="0" 
     aria-valuemax="100"
     aria-label="Upload progress">
  <div style="width: 65%"></div>
</div>

<!-- 文件列表 -->
<ul aria-label="Uploaded files">
  <li>document.pdf</li>
</ul>
```

---

## 11. 设计 Token

### 11.1 Tailwind 配置

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#EEF2FF',
          100: '#E0E7FF',
          500: '#6366F1',
          600: '#4F46E5',
          700: '#4338CA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'spin-slow': 'spin 3s linear infinite',
        'bounce-slow': 'bounce 2s infinite',
      },
    },
  },
};
```

---

## 12. 设计资源

### 12.1 Figma 结构

```
DocFormatConverter.fig
├── 📁 Design System
│   ├── 🎨 Colors
│   ├── 🔤 Typography
│   ├── 🧩 Components
│   └── 📐 Layout Grid
├── 📁 Pages
│   ├── 🏠 Home
│   ├── 🔄 Convert
│   ├── 📊 Dashboard
│   ├── 🔑 Login/Signup
│   └── ⚙️ Settings
└── 📁 Prototypes
    ├── 📱 Mobile
    └── 💻 Desktop
```

### 12.2 导出规范

| 资源 | 格式 | 尺寸 |
|------|------|------|
| Logo | SVG | 自适应 |
| Favicon | PNG/ICO | 32x32, 180x180 |
| OG Image | PNG | 1200x630 |
| Icons | SVG | 24x24 |
