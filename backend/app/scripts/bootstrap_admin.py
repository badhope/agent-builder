"""Bootstrap the initial admin user from ``BOOTSTRAP_ADMIN_*`` env vars.

Run with ``python -m app.scripts.bootstrap_admin``.
"""

from __future__ import annotations

import asyncio
from getpass import getpass

from app.db.models.user import UserPlan
from app.db.session import db_session
from app.logging_config import configure_logging, get_logger
from app.services.user_service import UserService
from app.settings import get_settings

logger = get_logger(__name__)


async def _run(email: str | None, password: str | None) -> None:
    settings = get_settings()
    if email is None:
        email = settings.bootstrap.email
    if password is None:
        # If password not given on CLI, fall back to env, otherwise prompt
        env_pwd = settings.bootstrap.password.get_secret_value() if settings.bootstrap.password else None
        password = env_pwd if env_pwd else getpass("Admin password: ")
    async with db_session() as session:
        svc = UserService(session)
        existing = await svc.get_by_email(email)
        if existing is not None:
            logger.info("admin.exists", email=email)
            return
        user = await svc.create(
            email=email,
            password=password,
            is_admin=True,
            plan=UserPlan.ENTERPRISE,
        )
        logger.info("admin.created", email=user.email, id=str(user.id))


def main() -> None:
    configure_logging()
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--email", default=None)
    p.add_argument("--password", default=None)
    args = p.parse_args()
    asyncio.run(_run(args.email, args.password))


if __name__ == "__main__":
    main()
