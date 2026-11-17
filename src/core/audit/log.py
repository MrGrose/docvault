import json
from typing import Any

from core.keys import AUDIT_SEQ_KEY, audit_key
from core.kv import LmdbKv, WriteTxn


def append_in_txn(txn: WriteTxn, record: dict[str, Any]) -> int:
    seq_raw = txn.get(AUDIT_SEQ_KEY)
    seq = int(seq_raw.decode("utf-8")) if seq_raw else 0
    seq += 1
    body = json.dumps({"seq": seq, **record}, ensure_ascii=False).encode("utf-8")
    txn.put(audit_key(seq), body)
    txn.put(AUDIT_SEQ_KEY, str(seq).encode("utf-8"))
    return seq


def list_records(kv: LmdbKv, from_seq: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    prefix = b"audit:"
    for key, raw in kv.scan(prefix):
        if key == AUDIT_SEQ_KEY:
            continue
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        seq = int(data.get("seq", 0))
        if seq < from_seq:
            continue
        out.append(data)
        if len(out) >= limit:
            break
    out.sort(key=lambda x: int(x.get("seq", 0)))
    return out
