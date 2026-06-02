"""Security core tests."""

from __future__ import annotations

import pytest

from app.core import security
from app.exceptions import AuthenticationError


def test_password_hash_round_trip():
    ph = security.PasswordManager()
    h = ph.hash("Sup3rStrong!Pass")
    assert ph.verify("Sup3rStrong!Pass", h)
    assert not ph.verify("wrong", h)


def test_jwt_round_trip():
    access, _access_exp = security.jwt_manager.issue_access_token(
        user_id="11111111-1111-1111-1111-111111111111",
        extra_claims={"role": "admin"},
    )
    refresh, _jti, _exp = security.jwt_manager.issue_refresh_token(
        user_id="11111111-1111-1111-1111-111111111111",
    )
    a = security.jwt_manager.verify_token(access, expected_type="access")
    assert a["sub"] == "11111111-1111-1111-1111-111111111111"
    assert a["role"] == "admin"
    r = security.jwt_manager.verify_token(refresh, expected_type="refresh")
    assert r["sub"] == "11111111-1111-1111-1111-111111111111"


def test_jwt_rejects_wrong_type():
    access, _exp = security.jwt_manager.issue_access_token(
        user_id="abc",
    )
    with pytest.raises(AuthenticationError):
        security.jwt_manager.verify_token(access, expected_type="refresh")


def test_api_key_generation_and_hash():
    key = security.generate_api_key()
    assert key.plaintext.startswith("dck_")
    assert key.hash is not None
    assert key.prefix is not None
    assert key.last4 is not None
    assert security.verify_api_key(key.plaintext, key.hash)
    assert not security.verify_api_key("dck_bogus", key.hash)


def test_signed_token_issuer_round_trip():
    issuer = security.SignedTokenIssuer(secret=b"a" * 32)
    token = issuer.issue(subject="file-123", ttl_s=60)
    payload = issuer.verify(token)
    assert payload["sub"] == "file-123"
    with pytest.raises(AuthenticationError):
        issuer.verify(token + "tampered")
    expired = issuer.issue(subject="file-123", ttl_s=-1)
    with pytest.raises(AuthenticationError):
        issuer.verify(expired)