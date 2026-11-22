from __future__ import annotations

import sys

import pytest

from app.domain.media import new_storage_key
from app.integrations.storage.local import InvalidStorageKeyError, LocalStorageBackend


def test_put_get_exists_delete_roundtrip(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = new_storage_key("image/jpeg")
    backend.put(key, b"datos-privados")
    assert backend.exists(key)
    assert backend.get(key) == b"datos-privados"
    backend.delete(key)
    assert not backend.exists(key)


def test_delete_is_idempotent_and_missing_file_is_missing(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = new_storage_key("image/png")
    backend.delete(key)  # no debe fallar
    with pytest.raises(FileNotFoundError):
        backend.get(key)


def test_refuses_to_overwrite_existing_key(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = new_storage_key("image/webp")
    backend.put(key, b"uno")
    with pytest.raises(RuntimeError):
        backend.put(key, b"dos")


def test_rejects_invalid_storage_key_and_path_traversal(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    for bad in [
        "../secret",
        "../../etc/passwd",
        "a/b/c.png",
        "..%2fsecret",
        "not-a-key",
        "",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa%2f../x.png",
    ]:
        with pytest.raises(InvalidStorageKeyError):
            backend.put(bad, b"x")
        with pytest.raises(InvalidStorageKeyError):
            backend.get(bad)


def test_storage_files_live_in_sharded_layout_not_at_root(tmp_path):
    backend = LocalStorageBackend(tmp_path)
    key = new_storage_key("image/png")
    backend.put(key, b"x")
    assert (tmp_path / key[:2] / key).is_file()
    assert not (tmp_path / key).is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_storage_files_are_written_with_600_permissions(tmp_path):
    import os

    backend = LocalStorageBackend(tmp_path)
    key = new_storage_key("image/jpeg")
    backend.put(key, b"x")
    mode = os.stat(tmp_path / key[:2] / key).st_mode & 0o777
    assert mode == 0o600
