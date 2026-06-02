"""Create a new API key for a user.

Run with ``python -m app.scripts.create_api_key <email> [--name ...] [--scopes ...]``.
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import db_session
from app.logging_config import configure_logging, get_logger
from app.services.api_key_service import create_key_for_user
from app.services.user_service import UserService

logger = get_logger(__name__)


async def _run(email: str, name: str, scopes: list[str], expires_in_days: int | None) -> None:
    async with db_session() as session:
        svc = UserService(session)
        user = await svc.get_by_email(email)
        if user is None:
            raise SystemExit(f"User not found: {email}")
        out = await create_key_for_user(
            session,
            user_id=str(user.id),
            name=name,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )
        print("API key created. Store this value now — it will not be shown again:")
        print(f"  {out['plain']}")
        print(f"id:    {out['id']}")
        print(f"scopes: {out['scopes']}")


def main() -> None:
    configure_logging()
    import argparse
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.create_api_key <email> [--name ...] [--scopes convert:read files:write]")
        sys.exit(2)
    p = argparse.ArgumentParser()
    p.add_argument("email")
    p.add_argument("--name", default="default")
    p.add_argument("--scopes", nargs="*", default=["convert:write", "files:read"])
    p.add_argument("--expires-in-days", type=int, default=None)
    args = p.parse_args()
    asyncio.run(_run(args.email, args.name, args.scopes, args.expires_in_days))


if __name__ == "__main__":
    main()
