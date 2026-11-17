import pytest

from core.errors import ConflictError
from core.keys import cs_key
from core.kv import LmdbKv


def test_cs_key_cannot_be_overwritten(tmp_path: pytest.TempPathFactory) -> None:
    kv = LmdbKv.open(tmp_path / "lmdb" / "x")
    key = cs_key("abc")
    kv.put_new(key, b"{}")
    with pytest.raises(ConflictError):
        kv.put_new(key, b'{"hack":1}')
    kv.close()
