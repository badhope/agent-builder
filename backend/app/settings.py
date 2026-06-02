"""Centralized, type-safe application configuration.

All runtime knobs flow through this module. Values are read once from
process environment / `.env` and frozen into a singleton ``Settings`` object.

Design notes
------------
* ``pydantic-settings`` is used for declarative, validated, immutable settings.
* Sensitive values (private key paths, S3 credentials) are loaded from env
  vars or mounted secret files. They are never logged.
* Nested grouping (``api``, ``db``, ``redis``, ...) keeps the public surface
  organised and consumable from dependency-injection code.
"""

from __future__ import annotations

import secrets
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import (
    Field,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Application environment identifier."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    TEST = "test"


class LogFormat(StrEnum):
    """Log output format."""

    JSON = "json"
    CONSOLE = "console"


class StorageBackend(StrEnum):
    """Storage adapter selection."""

    LOCAL = "local"
    S3 = "s3"


class RateLimiterKey(StrEnum):
    """What identifies a client in the rate limiter."""

    IP = "ip"
    USER = "user"
    APIKEY = "apikey"


# ---- Sub-configs -----------------------------------------------------------


class ApiSettings(BaseSettings):
    """HTTP API server settings."""

    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    root_path: str = ""
    cors_allow_origins: list[str] = Field(default_factory=list)
    trusted_hosts: list[str] = Field(default_factory=lambda: ["*"])
    behind_proxy: bool = False

    @field_validator("cors_allow_origins", "trusted_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return list(value)


class DatabaseSettings(BaseSettings):
    """Database connection settings (async + sync URLs)."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = Field(
        default="postgresql+asyncpg://docconverter:docconverter@localhost:5432/docconverter",
    )
    url_sync: str | None = None
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle_s: int = 3600
    echo: bool = False

    @model_validator(mode="after")
    def _derive_sync_url(self) -> DatabaseSettings:
        if not self.url_sync:
            self.url_sync = self.url.replace("+asyncpg", "+psycopg")
        return self


class RedisSettings(BaseSettings):
    """Redis connection settings (separate logical DBs for cache, broker, pubsub)."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    url: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]
    url_celery: RedisDsn | None = None
    url_pubsub: RedisDsn | None = None

    @model_validator(mode="after")
    def _derive(self) -> RedisSettings:
        base = str(self.url)
        if not self.url_celery:
            self.url_celery = _bump_db(base, 1)  # type: ignore[assignment]
        if not self.url_pubsub:
            self.url_pubsub = _bump_db(base, 2)  # type: ignore[assignment]
        return self


def _bump_db(url: str, db: int) -> str:
    """Switch a ``redis://host:port/N`` URL to db ``N``."""
    if "/" in url.rsplit(":", 1)[-1]:
        head, _, _ = url.rpartition("/")
        return f"{head}/{db}"
    return f"{url}/{db}"


class JwtSettings(BaseSettings):
    """JWT signing key configuration (RS256)."""

    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    algorithm: str = "RS256"
    issuer: str = "docformatconverter"
    audience: str = "docformatconverter-api"
    private_key_path: Path = Path("./keys/jwt_private.pem")
    public_key_path: Path = Path("./keys/jwt_public.pem")
    access_ttl_min: int = 30
    refresh_ttl_day: int = 30
    # SECURITY: auto_generate_keys defaults to True for developer convenience,
    # but the parent ``Settings`` validator forces it to False in production.
    # Multi-replica deployments MUST share a pre-generated keypair via
    # JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH; otherwise each replica
    # generates its own keypair and JWTs become invalid across replicas.
    auto_generate_keys: bool = True


class StorageSettings(BaseSettings):
    """Storage adapter configuration."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_", extra="ignore")

    backend: StorageBackend = StorageBackend.LOCAL
    local_root: Path = Path("./var/storage")
    public_base_url: str = ""
    presigned_ttl_s: int = 3600


class S3Settings(BaseSettings):
    """S3/MinIO connection settings."""

    model_config = SettingsConfigDict(env_prefix="S3_", extra="ignore")

    endpoint_url: str = "http://localhost:9000"
    region: str = "us-east-1"
    access_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    bucket: str = "conversions"
    use_ssl: bool = False
    addressing_style: str = "path"


class ConversionSettings(BaseSettings):
    """Conversion engine limits."""

    model_config = SettingsConfigDict(env_prefix="MAX_", extra="ignore")

    file_size_mb: int = 100
    batch_files: int = 50
    batch_total_size_mb: int = 500
    conversion_timeout_s: int = 300
    page_range: int = 1000

    @property
    def file_size_bytes(self) -> int:
        return self.file_size_mb * 1024 * 1024

    @property
    def batch_total_size_bytes(self) -> int:
        return self.batch_total_size_mb * 1024 * 1024


class WorkerSettings(BaseSettings):
    """Celery worker tuning."""

    model_config = SettingsConfigDict(env_prefix="CELERY_", extra="ignore")

    concurrency: int = 2
    prefetch_multiplier: int = 1
    task_time_limit_s: int = 600
    task_soft_time_limit_s: int = 540


class RateLimitSettings(BaseSettings):
    """Rate limiter thresholds and storage backend."""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", extra="ignore")

    default: str = "200/minute"
    convert: str = "10/minute"
    batch: str = "5/minute"
    auth: str = "20/minute"
    storage_backend: str = "local"
    key: RateLimiterKey = RateLimiterKey.IP


class AntivirusSettings(BaseSettings):
    """ClamAV scanner (optional)."""

    model_config = SettingsConfigDict(env_prefix="ANTIVIRUS_", extra="ignore")

    enabled: bool = False
    host: str = "clamav"
    port: int = 3310
    timeout_s: int = 30
    fail_open: bool = True  # allow upload on scanner error if true


class LoggingSettings(BaseSettings):
    """Logging + observability configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: str = "INFO"
    format: LogFormat = LogFormat.JSON
    file: Path | None = None


class TelemetrySettings(BaseSettings):
    """OpenTelemetry + Sentry."""

    model_config = SettingsConfigDict(extra="ignore")

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "docconverter-api"
    sentry_dsn: SecretStr = SecretStr("")


class SecurityHeadersSettings(BaseSettings):
    """Static security header values."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_", extra="ignore")

    hsts_enabled: bool = False
    hsts_max_age: int = 31_536_000
    referrer_policy: str = "no-referrer"


class BootstrapSettings(BaseSettings):
    """Bootstrap admin user (created on first start)."""

    model_config = SettingsConfigDict(env_prefix="BOOTSTRAP_ADMIN_", extra="ignore")

    enabled: bool = True
    email: str = "admin@example.com"
    # SECURITY: Default password must NEVER be used in production. The
    # parent ``Settings`` class performs the production-env check after
    # all sub-settings are constructed (see ``_propagate_env_to_subsystems``).
    password: SecretStr = SecretStr("ChangeMe!2026")


class WebhookSettings(BaseSettings):
    """Webhook delivery tuning."""

    model_config = SettingsConfigDict(env_prefix="WEBHOOK_", extra="ignore")

    timeout_s: int = 10
    max_attempts: int = 5
    backoff_base_s: int = 2


class RetentionSettings(BaseSettings):
    """File retention and soft-delete grace period settings."""

    model_config = SettingsConfigDict(env_prefix="RETENTION_", extra="ignore")

    # How long user-requested soft-deleted files stay restorable.
    soft_delete_grace_days: int = 7

    # Maximum number of rows to hard-delete per cleanup run (avoids OOM on huge batches).
    hard_delete_batch_size: int = 500


# ---- Root settings ----------------------------------------------------------


class Settings(BaseSettings):
    """Root settings aggregating all sub-configs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEV
    app_name: str = "DocFormatConverter"
    app_version: str = "1.0.0"
    app_debug: bool = False
    app_timezone: str = "UTC"
    app_secret_key: SecretStr = SecretStr(secrets.token_urlsafe(64))

    api: ApiSettings = Field(default_factory=ApiSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    conversion: ConversionSettings = Field(default_factory=ConversionSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    antivirus: AntivirusSettings = Field(default_factory=AntivirusSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    telemetry: TelemetrySettings = Field(
        default_factory=lambda: TelemetrySettings(
            _env_prefix="",
        )
    )
    security_headers: SecurityHeadersSettings = Field(default_factory=SecurityHeadersSettings)
    bootstrap: BootstrapSettings = Field(default_factory=BootstrapSettings)
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PROD

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.DEV

    @model_validator(mode="after")
    def _propagate_env_to_subsystems(self) -> Settings:
        """Pass the app_env down to sub-settings and enforce security rules.

        Runs AFTER all sub-settings are constructed, so we can:
        * Propagate ``app_env`` to every sub-config (so they can read
          ``_current_env`` and adjust validation strictness).
        * Re-check production-only invariants (e.g. default bootstrap password).
        """
        for sub in (
            self.bootstrap, self.api, self.db, self.redis, self.jwt,
            self.storage, self.s3, self.conversion, self.worker,
            self.rate_limit, self.antivirus, self.logging, self.telemetry,
            self.security_headers, self.webhook, self.retention,
        ):
            try:
                object.__setattr__(sub, "_current_env", self.app_env)
            except Exception:  # noqa: BLE001 - best-effort, never break settings load
                pass

        # SECURITY: Reject the well-known default bootstrap password in prod.
        if (
            self.app_env == AppEnv.PROD
            and self.bootstrap.password.get_secret_value() == "ChangeMe!2026"
        ):
            raise ValueError(
                "BOOTSTRAP_ADMIN_PASSWORD must be set to a strong value "
                "in production; the default is unsafe."
            )

        # SECURITY: Force auto_generate_keys=False in production so each
        # replica does not silently create its own keypair (which would
        # break JWT verification across replicas).
        if self.app_env == AppEnv.PROD and self.jwt.auto_generate_keys:
            raise ValueError(
                "JWT_AUTO_GENERATE_KEYS must be false in production; "
                "explicitly provision JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH "
                "via secrets/ConfigMap and share across all replicas."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide ``Settings`` singleton."""
    return Settings()  # type: ignore[call-arg]


# Convenience aliases ---------------------------------------------------------
settings: Settings = get_settings()
__all__ = [
    "AppEnv",
    "LogFormat",
    "RateLimiterKey",
    "Settings",
    "StorageBackend",
    "get_settings",
    "settings",
]
