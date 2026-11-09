"""Loader for the pinned guidance tables (sources + limits + advice lines)."""
import json
from functools import lru_cache
from pathlib import Path

GUIDANCE_DIR = Path(__file__).parent / "guidance"


@lru_cache(maxsize=1)
def sources() -> dict:
    data = json.loads((GUIDANCE_DIR / "sources.json").read_text(encoding="utf-8"))
    return {s["id"]: s for s in data["sources"]}


@lru_cache(maxsize=1)
def table() -> dict:
    return json.loads((GUIDANCE_DIR / "advice_table.json").read_text(encoding="utf-8"))


def limits() -> dict:
    return table()["limits"]


def lines() -> dict:
    return {line["id"]: line for line in table()["lines"]}


def mapping() -> dict:
    return table()["mapping"]


def param_key(name: str) -> str | None:
    """Map a parameter name as written in data ('Ecoil', 'Total arsenic') to a pinned key."""
    norm = " ".join((name or "").split()).lower()
    for key, lim in limits().items():
        if norm in (n.lower() for n in lim["names"]):
            return key
    return None
