"""Persistent + in-memory route cache."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_lock = threading.Lock()
_mem: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_dir() -> Path:
    base = os.environ.get("ORS_CACHE_DIR", ".cache/ors_routes")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _file_path(key: str) -> Path:
    safe = key.replace("/", "_").replace("\\", "_")[:200]
    return _cache_dir() / f"{safe}.json"


def make_route_key(
    lat1: float, lng1: float, lat2: float, lng2: float, profile: str,
) -> str:
    return (
        f"{profile}|{round(lat1, 4)}|{round(lng1, 4)}|"
        f"{round(lat2, 4)}|{round(lng2, 4)}"
    )


def get_cached(key: str, ttl_seconds: int) -> Optional[Dict[str, Any]]:
    now = time.time()
    with _lock:
        hit = _mem.get(key)
        if hit and now - hit[0] < ttl_seconds:
            return hit[1]
    fp = _file_path(key)
    if not fp.exists():
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        ts = float(data.get("_ts", 0))
        if now - ts >= ttl_seconds:
            return None
        payload = data.get("payload")
        if isinstance(payload, dict):
            with _lock:
                _mem[key] = (ts, payload)
            return payload
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def set_cached(key: str, payload: Dict[str, Any]) -> None:
    ts = time.time()
    with _lock:
        _mem[key] = (ts, payload)
    try:
        _file_path(key).write_text(
            json.dumps({"_ts": ts, "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_memory_cache() -> None:
    with _lock:
        _mem.clear()
