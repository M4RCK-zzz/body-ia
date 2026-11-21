from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.tokens import JwtTokenService, TokenError


def _service(secret: str = "a" * 40, ttl: timedelta = timedelta(minutes=30)) -> JwtTokenService:
    return JwtTokenService(secret=secret, algorithm="HS256", issuer="test", ttl=ttl)


def test_issue_and_verify_roundtrip():
    user_id = uuid.uuid4()
    service = _service()
    issued = service.issue(user_id)
    assert issued.expires_in == 1800
    assert service.verify(issued.value) == user_id


def test_expired_token_is_rejected():
    service = _service(ttl=timedelta(minutes=-1))
    with pytest.raises(TokenError):
        service.verify(service.issue(uuid.uuid4()).value)


def test_token_signed_with_other_secret_is_rejected():
    token = _service("a" * 40).issue(uuid.uuid4()).value
    with pytest.raises(TokenError):
        _service("b" * 40).verify(token)


def test_garbage_and_unsigned_tokens_are_rejected():
    service = _service()
    now = datetime.now(UTC)
    unsigned = jwt.encode(
        {"sub": str(uuid.uuid4()), "iss": "test", "iat": now, "exp": now + timedelta(minutes=5)},
        None,
        algorithm="none",
    )
    for bad in ("not-a-token", "", unsigned):
        with pytest.raises(TokenError):
            service.verify(bad)