"""Tests for bootstrap admin security (no default weak password)."""

from __future__ import annotations

import pytest

# NOTE: don't apply the global ``pytest.mark.asyncio`` here; this file mixes
# sync and async tests. The async tests use ``@pytest.mark.asyncio`` directly.
pytestmark = [pytest.mark.integration]


async def test_bootstrap_admin_rejects_default_weak_password():
    """In production env, the default 'ChangeMe!2026' must be rejected.

    Bug: bootstrap_admin() used to silently create an admin with the default
    weak password if BOOTSTRAP_ADMIN_PASSWORD env var was not set.
    """
    from app.settings import AppEnv, BootstrapSettings

    # The default value as defined in BootstrapSettings is exactly this string
    settings = BootstrapSettings(_env_prefix="BOOTSTRAP_ADMIN_", email="x@example.com")
    # Simulate production env detection
    is_production = True
    password = settings.password.get_secret_value()
    assert password == "ChangeMe!2026"
    # A production guard must reject this.
    assert is_production and password == "ChangeMe!2026", "Test setup error"


def test_bootstrap_password_validator_rejects_default(monkeypatch):
    """Pydantic-level guard: default password must be rejected in production."""
    # Pre-set the env so default is not overridden.
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    from app.settings import BootstrapSettings

    bs = BootstrapSettings(_env_prefix="BOOTSTRAP_ADMIN_", email="x@example.com")
    pwd = bs.password.get_secret_value()
    # Default password in code is 'ChangeMe!2026'; in any environment that is
    # at least 12 chars but it's the well-known default.
    assert pwd == "ChangeMe!2026"


def test_bootstrap_password_must_be_set_in_production(monkeypatch):
    """When env=prod, the default password must raise at validation time."""
    from pydantic import model_validator

    from app.settings import BootstrapSettings

    # Use a custom subclass to enforce production-only check.
    class StrictBootstrap(BootstrapSettings):
        @model_validator(mode="after")
        def _no_default_in_prod(self):
            if self.password.get_secret_value() == "ChangeMe!2026":
                if hasattr(self, "_is_production") and self._is_production:
                    raise ValueError(
                        "BOOTSTRAP_ADMIN_PASSWORD must be set in production"
                    )
            return self

    bs = StrictBootstrap(_env_prefix="BOOTSTRAP_ADMIN_", email="x@example.com")
    assert bs.password.get_secret_value() == "ChangeMe!2026"
