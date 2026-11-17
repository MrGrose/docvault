import hashlib
import json
from typing import Any

from core.cdc.buzhash import chunk_bytes
from core.keys import blob_key, chunk_key, tree_key
from core.kv import LmdbKv, WriteTxn


def _canonical_tree(paths: dict[str, str]) -> bytes:
    payload = json.dumps(paths, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return payload


def _manifest_chunk_hashes(raw: bytes) -> list[str]:
    loaded = json.loads(raw.decode("utf-8"))
    if not isinstance(loaded, list):
        return []
    return [str(x) for x in loaded]


class BlobStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def _store_chunk(self, chunk: bytes) -> str:
        digest = hashlib.sha256(chunk).hexdigest()
        key = chunk_key(digest)
        if self._kv.get(key) is None:
            self._kv.put_new(key, chunk)
        return digest

    def _store_chunk_in_txn(self, txn: WriteTxn, chunk: bytes) -> str:
        digest = hashlib.sha256(chunk).hexdigest()
        key = chunk_key(digest)
        if txn.get(key) is None:
            txn.put(key, chunk)
        return digest

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        body_key = blob_key(digest)
        existing = self._kv.get(body_key)
        if existing is not None and existing[:1] == b"[":
            return digest

        chunks = chunk_bytes(data)
        chunk_hashes = [self._store_chunk(c) for c in chunks]
        manifest = json.dumps(chunk_hashes, ensure_ascii=False).encode("utf-8")
        if existing is None:
            self._kv.put_new(body_key, manifest)
        return digest

    def put_in_txn(self, txn: WriteTxn, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        body_key = blob_key(digest)
        existing = txn.get(body_key)
        if existing is not None and existing[:1] == b"[":
            return digest

        chunks = chunk_bytes(data)
        chunk_hashes = [self._store_chunk_in_txn(txn, c) for c in chunks]
        manifest = json.dumps(chunk_hashes, ensure_ascii=False).encode("utf-8")
        if existing is None:
            txn.put_new(body_key, manifest)
        return digest

    def read(self, blob_hash: str) -> bytes:
        raw = self._kv.get(blob_key(blob_hash))
        if raw is None:
            msg = f"blob не найден: {blob_hash}"
            raise KeyError(msg)
        if raw[:1] == b"[":
            chunk_hashes = _manifest_chunk_hashes(raw)
            parts: list[bytes] = []
            for ch in chunk_hashes:
                part = self._kv.get(chunk_key(ch))
                if part is None:
                    msg = f"chunk не найден: {ch}"
                    raise KeyError(msg)
                parts.append(part)
            return b"".join(parts)
        return raw

    def chunk_hashes(self, blob_hash: str) -> list[str]:
        raw = self._kv.get(blob_key(blob_hash))
        if raw is None:
            msg = f"blob не найден: {blob_hash}"
            raise KeyError(msg)
        if raw[:1] == b"[":
            return _manifest_chunk_hashes(raw)
        return [hashlib.sha256(raw).hexdigest()]

    def diff(self, hash_a: str, hash_b: str) -> list[dict[str, Any]]:
        a = self.chunk_hashes(hash_a)
        b = self.chunk_hashes(hash_b)
        max_len = max(len(a), len(b))
        out: list[dict[str, Any]] = []
        for i in range(max_len):
            ca = a[i] if i < len(a) else None
            cb = b[i] if i < len(b) else None
            if ca == cb:
                continue
            out.append({"index": i, "before": ca, "after": cb})
        return out

    def put_tree(self, paths: dict[str, str]) -> str:
        body = _canonical_tree(paths)
        digest = hashlib.sha256(body).hexdigest()
        key = tree_key(digest)
        if self._kv.get(key) is None:
            self._kv.put_new(key, body)
        return digest

    def put_tree_in_txn(self, txn: WriteTxn, paths: dict[str, str]) -> str:
        body = _canonical_tree(paths)
        digest = hashlib.sha256(body).hexdigest()
        key = tree_key(digest)
        if txn.get(key) is None:
            txn.put(key, body)
        return digest

    def read_tree(self, tree_hash: str) -> dict[str, str]:
        raw = self._kv.get(tree_key(tree_hash))
        if raw is None:
            msg = f"tree не найден: {tree_hash}"
            raise KeyError(msg)
        data: dict[str, str] = json.loads(raw.decode("utf-8"))
        return data

    def diff_trees(self, tree_a: str, tree_b: str) -> list[dict[str, Any]]:
        a = self.read_tree(tree_a)
        b = self.read_tree(tree_b)
        paths = sorted(set(a) | set(b))
        out: list[dict[str, Any]] = []
        for path in paths:
            ha = a.get(path)
            hb = b.get(path)
            if ha == hb:
                continue
            out.append({"path": path, "before": ha, "after": hb})
        return out
