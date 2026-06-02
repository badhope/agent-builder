"""Email delivery service.

In production this uses SMTP (aiosmtplib). In dev mode (``APP_ENV=dev``)
emails are written to the console and the structured log so the developer
sees the rendered template without having to spin up a mail catcher.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.logging_config import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class EmailMessageSpec:
    to: str
    subject: str
    body_text: str
    body_html: str | None = None
    from_addr: str | None = None
    reply_to: str | None = None
    headers: dict[str, str] | None = None


class EmailService:
    """Send transactional email."""

    def __init__(self) -> None:
        self._settings = get_settings().email if hasattr(get_settings(), "email") else None
        # We don't have an email settings group, so derive defaults from env
        self._host = os.getenv("SMTP_HOST", "")
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._user = os.getenv("SMTP_USER", "")
        self._password = os.getenv("SMTP_PASSWORD", "")
        self._from = os.getenv("SMTP_FROM", "no-reply@docformatconverter.local")
        self._use_tls = os.getenv("SMTP_TLS", "starttls").lower() in {"1", "true", "starttls"}
        self._use_ssl = os.getenv("SMTP_TLS", "").lower() == "ssl"
        self._timeout = int(os.getenv("SMTP_TIMEOUT", "15"))
        self._template_env = Environment(
            loader=FileSystemLoader(
                os.path.join(
                    os.path.dirname(__file__), "..", "templates", "email",
                )
            ),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )

    @property
    def enabled(self) -> bool:
        return (bool(self._host) and get_settings().is_development is not False) or bool(self._host)

    async def send(self, spec: EmailMessageSpec) -> bool:
        """Send ``spec``; return True on success. Never raises into the caller."""
        try:
            message = self._build_message(spec)
            if not self._host:
                # Dev / no SMTP: log it.
                logger.info(
                    "email.dev_send",
                    to=spec.to,
                    subject=spec.subject,
                    body=spec.body_text[:512],
                )
                return True
            await asyncio.to_thread(self._send_sync, message)
            logger.info("email.sent", to=spec.to, subject=spec.subject)
            return True
        except Exception as exc:
            logger.warning(
                "email.send_failed", to=spec.to, error=str(exc),
            )
            return False

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body: str | None = None,
        template: str | None = None,
        context: dict[str, Any] | None = None,
        html: str | None = None,
    ) -> bool:
        """Convenience helper: render a template (or pass-through) and send."""
        if template:
            text, html_body = self.render_template(template, context or {})
            body = body or text
            html = html or html_body
        if not body:
            body = ""
        spec = EmailMessageSpec(
            to=to,
            subject=subject,
            body_text=body,
            body_html=html,
        )
        return await self.send(spec)

    # ---- templates ----

    def render_template(
        self, template_name: str, context: dict[str, Any],
    ) -> tuple[str, str]:
        """Return ``(text, html)`` for a template under ``app/templates/email``."""
        try:
            tmpl = self._template_env.get_template(f"{template_name}.html")
            html = tmpl.render(**context)
        except Exception:
            html = ""
        try:
            tmpl_text = self._template_env.get_template(f"{template_name}.txt")
            text = tmpl_text.render(**context)
        except Exception:
            text = html or ""
        return text, html

    # ---- internal ----

    def _build_message(self, spec: EmailMessageSpec) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr(
            ("DocFormatConverter", spec.from_addr or self._from),
        )
        msg["To"] = spec.to
        msg["Subject"] = spec.subject
        msg["Date"] = format_datetime(None)
        if spec.reply_to:
            msg["Reply-To"] = spec.reply_to
        for k, v in (spec.headers or {}).items():
            msg[k] = v
        msg.set_content(spec.body_text)
        if spec.body_html:
            msg.add_alternative(spec.body_html, subtype="html")
        return msg

    def _send_sync(self, message: EmailMessage) -> None:
        if self._use_ssl:
            with smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout,
            ) as smtp:
                if self._user:
                    smtp.login(self._user, self._password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.ehlo()
                if self._use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if self._user:
                    smtp.login(self._user, self._password)
                smtp.send_message(message)


# Module-level singleton
email_service = EmailService()


__all__ = ["EmailMessageSpec", "EmailService", "email_service"]
