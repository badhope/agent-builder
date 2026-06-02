"""Management scripts.

Run with ``python -m app.scripts.<name>``.
"""

from app.scripts import bootstrap_admin, create_api_key, generate_jwt_keys

__all__ = ["bootstrap_admin", "create_api_key", "generate_jwt_keys"]
