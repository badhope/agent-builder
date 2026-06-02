"""Initial unified schema for DocFormatConverter v1.0.

Revision ID: 0001
Revises:
Create Date: 2026-06-01

Single atomic migration that creates every table, enum, index, and trigger
the unified design needs. Subsequent migrations must be additive and
small.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ---- Enums ----
    user_plan = postgresql.ENUM("free", "pro", "enterprise", name="user_plan")
    user_role = postgresql.ENUM("user", "moderator", "admin", name="user_role")
    task_state = postgresql.ENUM(
        "pending", "queued", "running", "succeeded",
        "failed", "cancelled", "expired", name="task_state",
    )
    task_priority = postgresql.ENUM("low", "normal", "high", name="task_priority")
    file_purpose = postgresql.ENUM(
        "source", "output", "asset", "avatar", "thumbnail", name="file_purpose",
    )
    file_scan_status = postgresql.ENUM(
        "pending", "clean", "infected", "error", "skipped", name="file_scan_status",
    )
    log_level = postgresql.ENUM(
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", name="log_level",
    )
    webhook_delivery_status = postgresql.ENUM(
        "pending", "delivered", "failed", "cancelled", name="webhook_delivery_status",
    )
    token_purpose = postgresql.ENUM(
        "email_verify", "password_reset", "apikey_confirm",
        "totp_challenge", "account_delete", name="token_purpose",
    )
    for e in (
        user_plan, user_role, task_state, task_priority, file_purpose,
        file_scan_status, log_level, webhook_delivery_status, token_purpose,
    ):
        e.create(op.get_bind(), checkfirst=True)

    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_lower", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("plan", user_plan, nullable=False, server_default="free"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True)),
        sa.Column("quota_conversions_per_day", sa.Integer, nullable=False, server_default="100"),
        sa.Column("quota_storage_mb", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("quota_max_file_size_mb", sa.Integer, nullable=False, server_default="100"),
        sa.Column("quota_concurrent_tasks", sa.Integer, nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip", sa.String(64)),
        sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("totp_secret_enc", sa.Text),
        sa.Column("totp_enrolled_at", sa.DateTime(timezone=True)),
        sa.Column("recovery_codes_hash", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("webhook_secret", sa.String(64), nullable=False, server_default=""),
        sa.Column("preferences", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_plan", "users", ["plan"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.create_index("ix_users_active_verified", "users", ["is_active", "is_verified"])

    # ---- api_keys ----
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("key_last4", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", postgresql.INET),
        sa.Column("use_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(255)),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_user_active", "api_keys", ["user_id", "is_active"])
    op.create_index("ix_api_keys_active_expires", "api_keys", ["is_active", "expires_at"])
    op.create_index("ix_api_keys_expires_at", "api_keys", ["expires_at"])

    # ---- files (must exist before tasks due to FK) ----
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("batches.id", ondelete="SET NULL")),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("storage_bucket", sa.String(120)),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, server_default="source"),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(150)),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("format", sa.String(20)),
        sa.Column("scan_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("scan_signature", sa.String(255)),
        sa.Column("scan_at", sa.DateTime(timezone=True)),
        sa.Column("scan_engine", sa.String(60)),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("thumbnail_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("last_download_ip", postgresql.INET),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_reason", sa.String(120)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_files_owner_id", "files", ["owner_id"])
    op.create_index("ix_files_task_id", "files", ["task_id"])
    op.create_index("ix_files_batch_id", "files", ["batch_id"])
    op.create_index("ix_files_storage_key", "files", ["storage_key"])
    op.create_index("ix_files_purpose", "files", ["purpose"])
    op.create_index("ix_files_format", "files", ["format"])
    op.create_index("ix_files_sha256", "files", ["sha256"])
    op.create_index("ix_files_owner_purpose", "files", ["owner_id", "purpose"])
    op.create_index("ix_files_owner_created", "files", ["owner_id", "created_at"])
    op.create_index("ix_files_expires_at", "files", ["expires_at"])
    op.create_index("ix_files_deleted_at", "files", ["deleted_at"])
    op.create_index("ix_files_active", "files", ["expires_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ---- batches ----
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("running", sa.Integer, nullable=False, server_default="0"),
        sa.Column("archive_file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("archive_format", sa.String(20), nullable=False, server_default="zip"),
        sa.Column("webhook_url", sa.Text),
        sa.Column("webhook_secret", sa.String(64)),
        sa.Column("webhook_delivered", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("webhook_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_batches_owner_id", "batches", ["owner_id"])
    op.create_index("ix_batches_state", "batches", ["state"])
    op.create_index("ix_batches_owner_state", "batches", ["owner_id", "state"])
    op.create_index("ix_batches_idempotency_key", "batches", ["idempotency_key"])
    op.create_index("ix_batches_expires_at", "batches", ["expires_at"])

    # ---- tasks ----
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("batches.id", ondelete="SET NULL")),
        sa.Column("batch_index", sa.Integer),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_format", sa.String(20), nullable=False),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("target_format", sa.String(20), nullable=False),
        sa.Column("options_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("backend", sa.String(60)),
        sa.Column("output_file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("output_format", sa.String(20)),
        sa.Column("output_size", sa.Integer),
        sa.Column("output_sha256", sa.String(64)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text),
        sa.Column("error_details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("progress_pct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(255)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("webhook_url", sa.Text),
        sa.Column("webhook_secret", sa.String(64)),
        sa.Column("webhook_delivered", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("webhook_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("webhook_last_error", sa.Text),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("queue_time_ms", sa.Integer),
        sa.Column("processing_time_ms", sa.Integer),
        sa.Column("idempotency_key", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("progress_pct BETWEEN 0 AND 100", name="ck_tasks_progress_range"),
        sa.CheckConstraint("attempts >= 0", name="ck_tasks_attempts_nonneg"),
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_index("ix_tasks_batch_id", "tasks", ["batch_id"])
    op.create_index("ix_tasks_source_file_id", "tasks", ["source_file_id"])
    op.create_index("ix_tasks_source_format", "tasks", ["source_format"])
    op.create_index("ix_tasks_target_format", "tasks", ["target_format"])
    op.create_index("ix_tasks_state", "tasks", ["state"])
    op.create_index("ix_tasks_owner_state", "tasks", ["owner_id", "state"])
    op.create_index("ix_tasks_state_created", "tasks", ["state", "created_at"])
    op.create_index("ix_tasks_state_priority", "tasks", ["state", "priority", "created_at"])
    op.create_index("ix_tasks_expires_at", "tasks", ["expires_at"])
    op.create_index("ix_tasks_idempotency_key", "tasks", ["idempotency_key"])

    # ---- task_logs ----
    op.create_table(
        "task_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer, nullable=False, server_default="20"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])
    op.create_index("ix_task_logs_created_at", "task_logs", ["created_at"])
    op.create_index("ix_task_logs_errors", "task_logs", ["level"],
                    postgresql_where=sa.text("level >= 40"))

    # ---- batch_logs ----
    op.create_table(
        "batch_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_batch_logs_batch_id", "batch_logs", ["batch_id"])
    op.create_index("ix_batch_logs_event", "batch_logs", ["event"])
    op.create_index("ix_batch_logs_created_at", "batch_logs", ["created_at"])

    # ---- audit_logs ----
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_api_key_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("api_keys.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(64)),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # ---- webhook_subscriptions ----
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("description", sa.String(200)),
        sa.Column("events", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("secret", sa.String(64)),
        sa.Column("filter", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.Integer),
        sa.Column("last_error", sa.Text),
        sa.Column("total_delivered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_webhook_sub_user_id", "webhook_subscriptions", ["user_id"])
    op.create_index("ix_webhook_sub_user_active", "webhook_subscriptions", ["user_id", "is_active"])
    op.create_index("ix_webhook_sub_event", "webhook_subscriptions", ["events"], postgresql_using="gin")

    # ---- webhook_deliveries ----
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("secret_used", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer),
        sa.Column("response_body", sa.Text),
        sa.Column("response_headers", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("remote_ip", postgresql.INET),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_webhook_delivery_sub", "webhook_deliveries", ["subscription_id"])
    op.create_index("ix_webhook_delivery_user", "webhook_deliveries", ["user_id"])
    op.create_index("ix_webhook_delivery_event", "webhook_deliveries", ["event_type"])
    op.create_index("ix_webhook_delivery_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_delivery_next_attempt", "webhook_deliveries", ["next_attempt_at"],
                    postgresql_where=sa.text("status = 'pending'"))
    op.create_index("ix_webhook_delivery_created", "webhook_deliveries", ["created_at"])

    # ---- verification_tokens ----
    op.create_table(
        "verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(20), nullable=False),
        sa.Column("context", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_ip", postgresql.INET),
        sa.Column("created_user_agent", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_vt_user_id", "verification_tokens", ["user_id"])
    op.create_index("ix_vt_purpose", "verification_tokens", ["purpose"])
    op.create_index("ix_vt_token_hash", "verification_tokens", ["token_hash"], unique=True)
    op.create_index("ix_vt_expires_at", "verification_tokens", ["expires_at"])
    op.create_index("ix_vt_user_purpose_active", "verification_tokens", ["user_id", "purpose"])

    # ---- idempotency_records ----
    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("response_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_headers", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("in_flight", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "method", "path", "key", name="uq_idem_user_path_key"),
    )
    op.create_index("ix_idem_expires_at", "idempotency_records", ["expires_at"])
    op.create_index("ix_idem_in_flight", "idempotency_records", ["in_flight"])

    # ---- usage_counters ----
    op.create_table(
        "usage_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bytes_uploaded", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("bytes_downloaded", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("api_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("webhook_calls", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "day", name="uq_usage_user_day"),
    )
    op.create_index("ix_usage_user_day", "usage_counters", ["user_id", "day"])
    op.create_index("ix_usage_day", "usage_counters", ["day"])

    # ---- updated_at triggers ----
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for tbl in ("users", "tasks", "batches", "webhook_subscriptions", "files"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for tbl in (
        "webhook_deliveries", "webhook_subscriptions", "idempotency_records",
        "verification_tokens", "usage_counters",
        "audit_logs", "batch_logs", "task_logs", "files",
        "tasks", "batches", "api_keys", "users",
    ):
        op.drop_table(tbl)

    for tbl in ("users", "tasks", "batches", "webhook_subscriptions", "files"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_updated_at ON {tbl}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    for name in (
        "token_purpose", "webhook_delivery_status", "log_level", "file_scan_status",
        "file_purpose", "task_priority", "task_state", "user_role", "user_plan",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
