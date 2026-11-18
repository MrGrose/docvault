def head_key(space: str) -> bytes:
    return f"head:{space}".encode()


def draft_key(draft_id: str) -> bytes:
    return f"draft:{draft_id}".encode()


def cs_key(cs_id: str) -> bytes:
    return f"cs:{cs_id}".encode()


def blob_key(blob_hash: str) -> bytes:
    return f"blob:{blob_hash}".encode()


def chunk_key(chunk_hash: str) -> bytes:
    return f"chunk:{chunk_hash}".encode()


def tree_key(tree_hash: str) -> bytes:
    return f"tree:{tree_hash}".encode()


def idem_key(scope_id: str) -> bytes:
    return f"idem:{scope_id}".encode()


def run_key(run_id: str) -> bytes:
    return f"run:{run_id}".encode()


def audit_key(seq: int) -> bytes:
    return f"audit:{seq:020d}".encode()


AUDIT_SEQ_KEY = b"audit:seq"


DEFAULT_SPACE = "default"
DEFAULT_OWNER = "user:host"
