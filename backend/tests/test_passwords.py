from __future__ import annotations

from app.core.passwords import Argon2PasswordHasher


def test_hash_and_verify():
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash("Correcta-12345")
    assert hashed.startswith("$argon2id$")
    assert hasher.verify(hashed, "Correcta-12345") is True


def test_wrong_password_is_false():
    hasher = Argon2PasswordHasher()
    assert hasher.verify(hasher.hash("Correcta-12345"), "otra") is False


def test_invalid_hash_is_false_not_exception():
    assert Argon2PasswordHasher().verify("esto-no-es-un-hash", "x") is False