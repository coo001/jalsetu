"""Anonymous in-memory usage counters (deployment fact, not impact).

Stores only counts keyed by UTC date and a fixed counter name (route template,
packet status, or "print"). Never stores IP, user agent, cookies, query strings,
sample ids or any other identifier. Free hosts have an ephemeral filesystem, so
snapshots go to stdout only.
"""
import json
import os
import sys
import threading
from datetime import datetime, timezone

NOTE = "Anonymous page counters since the last restart of a free instance. Not users, not outcomes, not impact."
ROUTES = {"/", "/queue", "/sample/{id}", "/sources", "/eval", "/api/packet/{id}"}
BOT_TOKENS = ("bot", "spider", "crawl", "render")
HEALTH_PATHS = {"/healthz"}
SNAPSHOT_EVERY = 50

_lock = threading.Lock()
_counts: dict[str, dict[str, int]] = {}
_events = 0
SINCE_UTC = datetime.now(timezone.utc).isoformat(timespec="seconds")


def enabled() -> bool:
    return os.environ.get("JALSETU_DISABLE_USAGE") != "1"


def is_bot(user_agent: str | None) -> bool:
    ua = (user_agent or "").lower()
    return any(t in ua for t in BOT_TOKENS)


def should_count(path: str, user_agent: str | None) -> bool:
    """UA is inspected only here and never stored."""
    return enabled() and path not in HEALTH_PATHS and not is_bot(user_agent)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def record(name: str) -> None:
    """name must be a fixed route template, 'status:<status>' or 'print'."""
    global _events
    if not enabled():
        return
    with _lock:
        day = _counts.setdefault(_today(), {})
        day[name] = day.get(name, 0) + 1
        _events += 1
        due = _events % SNAPSHOT_EVERY == 0
    if due:
        log_snapshot()


def snapshot() -> dict:
    with _lock:
        return {d: dict(c) for d, c in _counts.items()}


def log_snapshot() -> None:
    print(json.dumps({"usage_snapshot": snapshot(), "since_utc": SINCE_UTC}), file=sys.stdout, flush=True)


def stats() -> dict:
    return {"counters": snapshot(), "since_utc": SINCE_UTC, "note": NOTE, "enabled": enabled()}


def reset() -> None:
    global _events
    with _lock:
        _counts.clear()
        _events = 0
