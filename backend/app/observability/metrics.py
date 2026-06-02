"""Prometheus metrics."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUEST_LATENCY = Histogram(
    "docconv_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path", "status"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

REQUEST_TOTAL = Counter(
    "docconv_http_requests_total",
    "Total HTTP requests.",
    labelnames=("method", "path", "status"),
)

CONVERSION_LATENCY = Histogram(
    "docconv_conversion_duration_seconds",
    "Conversion wall-clock duration.",
    labelnames=("source", "target", "backend", "status"),
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)

CONVERSION_TOTAL = Counter(
    "docconv_conversions_total",
    "Total conversions processed.",
    labelnames=("source", "target", "backend", "status"),
)

QUEUE_DEPTH = Gauge(
    "docconv_queue_depth",
    "Number of pending tasks in the Celery queue.",
    labelnames=("queue",),
)

WORKER_ACTIVE = Gauge(
    "docconv_worker_active",
    "Number of currently-active worker processes.",
)

UPLOAD_BYTES = Counter(
    "docconv_upload_bytes_total",
    "Total bytes uploaded.",
    labelnames=("format",),
)

DOWNLOAD_BYTES = Counter(
    "docconv_download_bytes_total",
    "Total bytes downloaded.",
)

AUTH_ATTEMPTS = Counter(
    "docconv_auth_attempts_total",
    "Authentication attempts by outcome.",
    labelnames=("method", "outcome"),
)


__all__ = [
    "AUTH_ATTEMPTS",
    "CONVERSION_LATENCY",
    "CONVERSION_TOTAL",
    "DOWNLOAD_BYTES",
    "QUEUE_DEPTH",
    "REQUEST_LATENCY",
    "REQUEST_TOTAL",
    "UPLOAD_BYTES",
    "WORKER_ACTIVE",
]
