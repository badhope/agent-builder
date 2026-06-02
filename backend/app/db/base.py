"""Re-export of the SQLAlchemy declarative base for Alembic autogen.

This module exists so that ``target_metadata = app.db.base.Base`` works
from the Alembic ``env.py`` without having to depend on the full
session module (which would also import the engine factory, the
DB session factory, and the redis client). Keeping the import surface
narrow keeps ``alembic`` migrations independent of the runtime
configuration.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common declarative base for all ORM models.

    All models in :mod:`app.db.models` inherit from this class via
    re-export from :mod:`app.db.session`. Keeping the actual class
    here means that even a partial import (e.g. for tooling that just
    needs to walk the metadata) doesn't pull in the async engine.
    """


__all__ = ["Base"]
