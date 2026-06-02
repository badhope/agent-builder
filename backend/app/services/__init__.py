"""Service layer — pure business logic, no FastAPI dependencies.

Each module exposes a single *Service class (or a small set of related
classes). Routes import only from :mod:`app.services`.
"""

from app.services.api_key_service import ApiKeyService, create_key_for_user
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService, TokenPair, bootstrap_admin
from app.services.batch_service import BatchService
from app.services.converter_dispatcher import ConverterDispatcher
from app.services.download_service import DownloadService
from app.services.email_service import EmailMessageSpec, EmailService, email_service
from app.services.idempotency_service import IdempotencyConflict, IdempotencyService, hash_request
from app.services.metadata_service import MetadataService, metadata_service
from app.services.quota_service import QuotaService
from app.services.storage_service import StorageService
from app.services.task_service import TaskService
from app.services.thumbnail_service import ThumbnailService, thumbnail_service
from app.services.totp_service import TotpEnrollment, TotpService
from app.services.user_service import UserService
from app.services.webhook_service import WebhookService

__all__ = [
    "ApiKeyService",
    "AuditService",
    "AuthService",
    "BatchService",
    "ConverterDispatcher",
    "DownloadService",
    "EmailMessageSpec",
    "EmailService",
    "IdempotencyConflict",
    "IdempotencyService",
    "MetadataService",
    "QuotaService",
    "StorageService",
    "TaskService",
    "ThumbnailService",
    "TokenPair",
    "TotpEnrollment",
    "TotpService",
    "UserService",
    "WebhookService",
    "bootstrap_admin",
    "create_key_for_user",
    "email_service",
    "hash_request",
    "metadata_service",
    "thumbnail_service",
]
