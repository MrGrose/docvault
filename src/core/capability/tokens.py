import base64
import binascii
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass

from core.errors import AuthzError


@dataclass(frozen=True)
class CapabilityClaims:
    space: str
    path_prefixes: tuple[str, ...]
    ops: tuple[str, ...]
    exp: int
    draft_id: str | None = None
    jti: str | None = None
    run_id: str | None = None
    agent_id: str | None = None


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()[:16]


def _secret() -> bytes:
    raw = os.environ.get("DOCVAULT_CAPABILITY_SECRET", "")
    if not raw:
        msg = "DOCVAULT_CAPABILITY_SECRET не задан"
        raise AuthzError(msg)
    return raw.encode("utf-8")


def _sign(payload_b64: str, secret: bytes) -> str:
    digest = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def issue_token(
    *,
    space: str,
    path_prefixes: list[str],
    ops: list[str],
    draft_id: str,
    ttl_seconds: int = 3600,
    jti: str | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
) -> str:
    secret = _secret()
    exp = int(time.time()) + ttl_seconds
    payload = {
        "space": space,
        "path_prefixes": path_prefixes,
        "ops": ops,
        "exp": exp,
        "draft_id": draft_id,
        "jti": jti or uuid.uuid4().hex,
        "run_id": run_id,
        "agent_id": agent_id,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    sig = _sign(payload_b64, secret)
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> CapabilityClaims:
    secret = _secret()
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = _sign(payload_b64, secret)
        if not hmac.compare_digest(expected, sig):
            raise AuthzError("подпись token не совпала")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        exp = int(data["exp"])
        space = str(data["space"])
        prefixes = tuple(str(x) for x in data["path_prefixes"])
        ops = tuple(str(x) for x in data["ops"])
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) as exc:
        raise AuthzError("неверный формат token") from exc
    if time.time() > exp:
        raise AuthzError("token истек")
    draft_raw = data.get("draft_id")
    jti_raw = data.get("jti")
    run_raw = data.get("run_id")
    agent_raw = data.get("agent_id")
    return CapabilityClaims(
        space=space,
        path_prefixes=prefixes,
        ops=ops,
        exp=exp,
        draft_id=str(draft_raw) if draft_raw else None,
        jti=str(jti_raw) if jti_raw else None,
        run_id=str(run_raw) if run_raw else None,
        agent_id=str(agent_raw) if agent_raw else None,
    )


def assert_path_allowed(claims: CapabilityClaims, path: str) -> None:
    if not any(path.startswith(prefix) for prefix in claims.path_prefixes):
        raise AuthzError(f"path вне разрешённых префиксов: {path}")


def assert_op_allowed(claims: CapabilityClaims, op: str) -> None:
    if op not in claims.ops:
        raise AuthzError(f"операция не разрешена: {op}")
