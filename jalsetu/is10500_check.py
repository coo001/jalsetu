"""Verdict of a parsed value against the pinned BIS IS 10500 limits."""
from . import pinned


def verdict(param_key: str, value: float, unit: str) -> dict:
    lim = pinned.limits()[param_key]
    perm = float(lim["permissible"])
    if param_key == "ecoli":
        exceeds = value > 0
        ratio = None
    else:
        exceeds = value > perm
        ratio = round(value / perm, 2)
    return {
        "param": param_key,
        "param_display": lim["display"],
        "exceeds": exceeds,
        "value": value,
        "unit": unit,
        "acceptable": lim["acceptable"],
        "permissible": lim["permissible"],
        "permissible_note": lim.get("permissible_note"),
        "ratio": ratio,
        "limit_ref": lim["ref"],
        "limit_source_ids": lim["source_ids"],
    }
