import pytest
import jwt as pyjwt

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    ALGORITHM,
)
from app.config import settings


def test_hash_password_returns_string():
    h = hash_password("s3cret!")
    assert isinstance(h, str)
    assert h != "s3cret!"


def test_hash_is_not_deterministic():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_correct():
    h = hash_password("correct-horse")
    assert verify_password("correct-horse", h) is True


def test_verify_password_wrong():
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-456")
    payload = decode_token(token)
    assert payload["sub"] == "user-456"
    assert payload["type"] == "refresh"


def test_decode_expired_token():
    expired_payload = {"sub": "x", "exp": 0, "type": "access"}
    token = pyjwt.encode(expired_payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token)


def test_decode_tampered_token():
    token = create_access_token("user-1")
    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(token, "wrong-key", algorithms=[ALGORITHM])
