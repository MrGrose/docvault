from core import kv


def test_import_kv() -> None:
    assert kv.MAP_SIZE > 0
