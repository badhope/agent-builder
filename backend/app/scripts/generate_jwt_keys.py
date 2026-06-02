"""Generate the JWT RS256 key pair used by the API.

Run with ``python -m app.scripts.generate_jwt_keys`` to write:

* ``keys/jwt_private.pem``  (RS256, 4096-bit)
* ``keys/jwt_public.pem``   (used by verifiers)

Existing files are not overwritten.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.logging_config import configure_logging, get_logger
from app.settings import get_settings

logger = get_logger(__name__)


def _key_dir() -> Path:
    s = get_settings()
    return Path(s.jwt.private_key_path).parent


def _write(path: Path, data: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        logger.info("key.exists", path=str(path))
        return
    path.write_bytes(data)
    try:
        path.chmod(mode)
    except Exception:
        pass
    logger.info("key.written", path=str(path))


def main() -> None:
    configure_logging()
    key_dir = _key_dir()
    priv_path = key_dir / "jwt_private.pem"
    pub_path = key_dir / "jwt_public.pem"

    if priv_path.exists() and pub_path.exists():
        logger.info("jwt.keys_present", dir=str(key_dir))
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write(priv_path, priv_pem, mode=0o600)
    _write(pub_path, pub_pem, mode=0o644)
    logger.info("jwt.keys_generated", dir=str(key_dir))


if __name__ == "__main__":
    main()
