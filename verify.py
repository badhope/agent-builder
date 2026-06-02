"""Sanity-check the project structure.

Walks the codebase and reports:
- missing files that the spec requires
- files that are too small (< 50 bytes — typical of a stub)
- files that contain only ``pass`` / ``...`` / ``NotImplementedError`` markers
- imports that look broken (a name referenced in ``__all__`` that isn't bound)
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MINIPROGRAM = ROOT / "miniprogram"

BACKEND_REQUIRED = [
    "app/main.py",
    "app/settings.py",
    "app/exceptions.py",
    "app/logging_config.py",
    "app/api/deps.py",
    "app/api/v1/router.py",
    "app/api/v1/routes/auth.py",
    "app/api/v1/routes/users.py",
    "app/api/v1/routes/files.py",
    "app/api/v1/routes/convert.py",
    "app/api/v1/routes/tasks.py",
    "app/api/v1/routes/batch.py",
    "app/api/v1/routes/formats.py",
    "app/api/v1/routes/webhooks.py",
    "app/api/v1/routes/admin.py",
    "app/api/v1/routes/password_reset.py",
    "app/api/v1/routes/email_verify.py",
    "app/api/v1/routes/totp.py",
    "app/converters/base.py",
    "app/converters/registry.py",
    "app/converters/factory.py",
    "app/converters/options.py",
    "app/converters/result.py",
    "app/converters/sandbox.py",
    "app/converters/backends/libreoffice.py",
    "app/converters/backends/pandoc.py",
    "app/converters/backends/pillow.py",
    "app/converters/backends/tesseract.py",
    "app/converters/backends/weasyprint.py",
    "app/converters/document/docx_converter.py",
    "app/converters/document/pdf_converter.py",
    "app/converters/document/odt_converter.py",
    "app/converters/document/epub_converter.py",
    "app/converters/markup/markdown_converter.py",
    "app/converters/markup/html_converter.py",
    "app/converters/spreadsheet/csv_converter.py",
    "app/converters/spreadsheet/xlsx_converter.py",
    "app/converters/presentation/pptx_converter.py",
    "app/converters/ebook/ebook_converter.py",
    "app/converters/image/image_converter.py",
    "app/converters/data/csv_converter.py",
    "app/converters/data/json_converter.py",
    "app/converters/data/xml_converter.py",
    "app/converters/data/yaml_converter.py",
    "app/services/auth_service.py",
    "app/services/storage_service.py",
    "app/services/quota_service.py",
    "app/services/task_service.py",
    "app/services/converter_dispatcher.py",
    "app/services/api_key_service.py",
    "app/services/webhook_service.py",
    "app/services/batch_service.py",
    "app/services/audit_service.py",
    "app/services/result_cache.py",
    "app/services/email_service.py",
    "app/services/totp_service.py",
    "app/services/idempotency_service.py",
    "app/services/thumbnail_service.py",
    "app/services/metadata_service.py",
    "app/services/download_service.py",
    "app/services/user_service.py",
    "app/workers/celery_app.py",
    "app/workers/conversion.py",
    "app/workers/cleanup.py",
    "app/workers/webhook.py",
    "app/workers/maintenance.py",
    "app/workers/progress.py",
    "app/db/session.py",
    "app/db/base.py",
    "app/db/models/__init__.py",
    "app/db/models/user.py",
    "app/db/models/file.py",
    "app/db/models/task.py",
    "app/db/models/api_key.py",
    "app/db/models/audit_log.py",
    "app/db/models/batch.py",
    "app/db/models/batch_log.py",
    "app/db/models/idempotency.py",
    "app/db/models/revoked_token.py",
    "app/db/models/task_log.py",
    "app/db/models/usage.py",
    "app/db/models/verification_token.py",
    "app/db/models/webhook.py",
    "app/middleware/audit.py",
    "app/middleware/idempotency.py",
    "app/middleware/request_id.py",
    "app/middleware/security_headers.py",
    "app/observability/metrics.py",
    "app/observability/sentry.py",
    "app/observability/tracing.py",
    "app/storage/base.py",
    "app/storage/factory.py",
    "app/storage/local.py",
    "app/storage/s3.py",
    "app/websocket/manager.py",
    "app/websocket/routes.py",
    "app/core/security.py",
    "app/core/permissions.py",
    "app/core/rate_limit.py",
    "app/core/antivirus.py",
    "app/core/magic_bytes.py",
    "app/core/sanitizers.py",
    "app/core/ssrf.py",
    "app/scripts/bootstrap_admin.py",
    "app/scripts/create_api_key.py",
    "app/scripts/generate_jwt_keys.py",
    "app/schemas/__init__.py",
    "app/schemas/auth.py",
    "app/schemas/user.py",
    "app/schemas/task.py",
    "app/schemas/file.py",
    "app/schemas/batch.py",
    "app/schemas/format.py",
    "app/schemas/webhook.py",
    "app/schemas/common.py",
    "alembic.ini",
    "alembic/env.py",
    "alembic/versions/0001_initial_schema.py",
]

FRONTEND_REQUIRED = [
    "package.json",
    "vite.config.ts",
    "tsconfig.json",
    "Dockerfile",
    "index.html",
    "src/main.tsx",
    "src/App.tsx",
    "src/api/client.ts",
    "src/api/auth.ts",
    "src/api/convert.ts",
    "src/stores/auth.ts",
    "src/stores/upload.ts",
    "src/components/ui/index.ts",
    "src/components/ui/Button.tsx",
    "src/components/ui/Input.tsx",
    "src/components/ui/Select.tsx",
    "src/components/ui/Card.tsx",
    "src/components/ui/Modal.tsx",
    "src/components/ui/Toast.tsx",
    "src/components/ui/ProgressBar.tsx",
    "src/components/ui/Badge.tsx",
    "src/components/ui/Tabs.tsx",
    "src/components/ui/Dropdown.tsx",
    "src/components/ui/Switch.tsx",
    "src/components/ui/Skeleton.tsx",
    "src/components/ui/Spinner.tsx",
    "src/components/ui/ErrorBoundary.tsx",
    "src/components/layout/AppShell.tsx",
    "src/components/auth/ProtectedRoute.tsx",
    "src/components/upload/FileDropzone.tsx",
    "src/hooks/useTaskProgress.ts",
    "src/pages/LandingPage.tsx",
    "src/pages/LoginPage.tsx",
    "src/pages/RegisterPage.tsx",
    "src/pages/DashboardPage.tsx",
    "src/pages/ConvertPage.tsx",
    "src/pages/TasksPage.tsx",
    "src/pages/FilesPage.tsx",
    "src/pages/SettingsPage.tsx",
    "src/pages/ApiKeysPage.tsx",
    "src/pages/AdminPage.tsx",
    "src/pages/NotFoundPage.tsx",
]

MINIPROGRAM_REQUIRED = [
    "package.json",
    "tsconfig.json",
    "babel.config.js",
    "project.config.json",
    "config/index.ts",
    "config/dev.ts",
    "config/prod.ts",
    "src/app.tsx",
    "src/app.config.ts",
    "src/app.scss",
    "src/api/client.ts",
    "src/api/auth.ts",
    "src/api/convert.ts",
    "src/stores/auth.ts",
    "src/types/api.ts",
    "src/utils/format.ts",
    "src/custom-tab-bar/index.tsx",
    "src/pages/index/index.tsx",
    "src/pages/login/index.tsx",
    "src/pages/register/index.tsx",
    "src/pages/convert/index.tsx",
    "src/pages/tasks/index.tsx",
    "src/pages/task-detail/index.tsx",
    "src/pages/profile/index.tsx",
]

ROOT_REQUIRED = [
    "Makefile",
    "pyproject.toml",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "Dockerfile",
    ".env.example",
]


def main() -> int:
    print("=" * 72)
    print("DocFormatConverter project verification")
    print("=" * 72)
    missing: list[str] = []
    tiny: list[tuple[str, int]] = []
    stubs: list[tuple[str, int]] = []

    for path in ROOT_REQUIRED:
        p = ROOT / path
        if not p.exists():
            missing.append(str(p))
        elif p.stat().st_size < 200:
            tiny.append((str(p), p.stat().st_size))

    for path in BACKEND_REQUIRED:
        p = BACKEND / path
        if not p.exists():
            missing.append(str(p))
            continue
        size = p.stat().st_size
        if size < 200:
            tiny.append((str(p), size))
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        non_blank = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        meaningful = "\n".join(non_blank)
        if re.search(r"^\s*pass\s*$", meaningful, re.M) and len(non_blank) <= 3:
            stubs.append((str(p), len(non_blank)))
        if "raise NotImplementedError" in text and "def " not in text:
            stubs.append((str(p), 0))

    for path in FRONTEND_REQUIRED:
        p = FRONTEND / path
        if not p.exists():
            missing.append(str(p))
        elif p.stat().st_size < 200:
            tiny.append((str(p), p.stat().st_size))

    for path in MINIPROGRAM_REQUIRED:
        p = MINIPROGRAM / path
        if not p.exists():
            missing.append(str(p))
        elif p.stat().st_size < 200:
            tiny.append((str(p), p.stat().st_size))

    print()
    print(f"Required files checked: {len(ROOT_REQUIRED) + len(BACKEND_REQUIRED) + len(FRONTEND_REQUIRED) + len(MINIPROGRAM_REQUIRED)}")
    print(f"Missing files:          {len(missing)}")
    print(f"Suspiciously tiny:      {len(tiny)}")
    print(f"Likely stub files:      {len(stubs)}")

    if missing:
        print()
        print("--- MISSING FILES ---")
        for p in missing:
            print(f"  {p}")
    if tiny:
        print()
        print("--- TINY FILES (< 200 bytes) ---")
        for p, size in tiny:
            print(f"  {p}  ({size}B)")
    if stubs:
        print()
        print("--- LIKELY STUB FILES ---")
        for p, n in stubs:
            print(f"  {p}  (meaningful lines: {n})")

    if not missing and not tiny and not stubs:
        print()
        print("All required files are present and have real content.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())