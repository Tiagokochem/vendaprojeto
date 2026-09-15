"""Rate limit simples em memória (webhook / abuso)."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def allow(key: str, *, limit: int = 60, window_seconds: int = 60) -> bool:
    """True se ainda cabe no bucket (sliding window)."""
    now = time.monotonic()
    with _lock:
        hits = _buckets[key]
        cutoff = now - window_seconds
        _buckets[key] = [t for t in hits if t >= cutoff]
        if len(_buckets[key]) >= limit:
            return False
        _buckets[key].append(now)
        return True
