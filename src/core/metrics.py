from threading import Lock
from typing import Any

_lock = Lock()
_counters: dict[str, float] = {}
_observations: dict[str, tuple[float, int]] = {}


def inc(name: str, value: float = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + value


def observe(name: str, seconds: float) -> None:
    with _lock:
        total, count = _observations.get(name, (0.0, 0))
        _observations[name] = (total + seconds, count + 1)


def snapshot() -> dict[str, Any]:
    with _lock:
        return {
            "counters": dict(_counters),
            "observations": {
                name: {"sum": total, "count": count}
                for name, (total, count) in _observations.items()
            },
        }


def render() -> str:
    with _lock:
        lines = []
        for name, value in sorted(_counters.items()):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value:g}")
        for name, (total, count) in sorted(_observations.items()):
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_sum {total:.6f}")
            lines.append(f"{name}_count {count}")
        return "\n".join(lines) + "\n"


def reset() -> None:
    with _lock:
        _counters.clear()
        _observations.clear()
