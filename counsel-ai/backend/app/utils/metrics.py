"""Minimal Prometheus-compatible metrics registry (zero dependencies).

Exposes counters, gauges and histograms in Prometheus text exposition format
at ``GET /metrics`` (when enabled). Intentionally dependency-free so the app
works offline; swap for prometheus-client without changing call sites if a
full metrics stack is ever required.
"""

from __future__ import annotations

import math
import threading
import time

_lock = threading.Lock()
_counters: dict[str, float] = {}
_gauges: dict[str, float] = {}
_histograms: dict[str, list[float]] = {}

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


def inc(name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
    with _lock:
        key = _key(name, labels)
        _counters[key] = _counters.get(key, 0.0) + value


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    with _lock:
        _gauges[_key(name, labels)] = value


def observe(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    with _lock:
        _histograms.setdefault(_key(name, labels), []).append(value)
        # bound memory on unbounded label sets
        if len(_histograms[_key(name, labels)]) > 100_000:
            del _histograms[_key(name, labels)][:50_000]


class timed:
    """Context manager / decorator recording seconds into a histogram."""

    def __init__(self, name: str, labels: dict[str, str] | None = None) -> None:
        self.name = name
        self.labels = labels

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        observe(self.name, time.perf_counter() - self._t0, self.labels)


def render() -> str:
    """Prometheus text exposition of all recorded metrics."""
    lines: list[str] = []
    with _lock:
        for key, val in sorted(_counters.items()):
            name, lstr = _split(key)
            lines.append(f"# TYPE {name} counter" if not any(
                l.startswith(f"# TYPE {name}") for l in lines) else "")
            lines.append(f"{name}{lstr} {val}")
        for key, val in sorted(_gauges.items()):
            name, lstr = _split(key)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{lstr} {val}")
        for key, values in sorted(_histograms.items()):
            base, lstr = _split(key)
            lines.append(f"# TYPE {base} histogram")
            buckets = DEFAULT_BUCKETS + (math.inf,)
            cum = 0
            vs = sorted(values)
            i = 0
            for b in buckets:
                while i < len(vs) and vs[i] <= b:
                    cum += 1
                    i += 1
                blabel = f'{lstr[:-1]},le="{b}"}}' if lstr else f'{{le="{b}"}}'
                lines.append(f"{base}_bucket{blabel} {cum}")
            lines.append(f"{base}_sum{lstr} {sum(vs)}")
            lines.append(f"{base}_count{lstr} {len(vs)}")
    return "\n".join(x for x in lines if x) + "\n"


# ------------------------------------------------------------------ helpers


def _key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    inner = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{inner}}}"


def _split(key: str) -> tuple[str, str]:
    if "{" in key:
        name, rest = key.split("{", 1)
        return name, "{" + rest
    return key, ""
