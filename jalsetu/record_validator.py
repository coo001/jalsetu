"""Stop rules: any reason here makes the record `needs_review` (except warnings)."""
from collections import Counter
from datetime import datetime

from . import pinned
from .snapshot import record_key
from .units import parse_value

REASON_CODES = [
    "VALUE_MISSING",
    "VALUE_NOT_NUMERIC",
    "UNIT_MISSING",
    "UNIT_MISMATCH",
    "UNKNOWN_PARAM",
    "LIMIT_MISMATCH",
    "BELOW_LIMIT_BUT_LISTED",
    "SAMPLE_ID_MISSING",
    "SAMPLE_ID_DUPLICATE",
    "TEST_DATE_INVALID",
]
WARNING_CODES = ["LAB_NOT_IN_L10"]

DATE_FMT = "%d/%m/%Y %H:%M:%S"


def norm_name(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


def _num(s) -> float | None:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def parse_test_date(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip(), DATE_FMT)
    except ValueError:
        return None


def validate(record: dict, key_counts: Counter, lab_names: set[str], snapshot_date: str) -> dict:
    """Return {'reasons': [{code, detail}], 'warnings': [...], 'lab_match': {...}}.

    key_counts: Counter of (sample_id, param) over the whole snapshot.
    lab_names: L10 lab names exactly as listed (normalization happens here).
    """
    reasons, warnings = [], []

    def add(code, detail):
        reasons.append({"code": code, "detail": detail})

    sid = (record.get("sample_id") or "").strip()
    if not sid:
        add("SAMPLE_ID_MISSING", "sample_id is empty")
    elif key_counts.get(record_key(record), 0) > 1:
        add("SAMPLE_ID_DUPLICATE", f"{sid} appears {key_counts[record_key(record)]} times for the same parameter in this snapshot")

    pk = pinned.param_key(record.get("param", ""))
    if pk is None:
        add("UNKNOWN_PARAM", f"parameter {record.get('param')!r} is not in the pinned limit table")

    pv = parse_value(record.get("value"))
    if pv["error"] == "missing":
        add("VALUE_MISSING", "value is empty")
    elif pv["error"] == "not_numeric":
        add("VALUE_NOT_NUMERIC", f"value {record.get('value')!r} is not a plain number")
    if pv["error"] != "missing":
        if pv["unit_raw"] is None:
            add("UNIT_MISSING", f"value {record.get('value')!r} has no unit")
        elif pk is not None and pv["unit"] != pinned.limits()[pk]["unit"]:
            add("UNIT_MISMATCH", f"unit {pv['unit_raw']!r} != pinned unit {pinned.limits()[pk]['unit']!r}")

    if pk is not None:
        lim = pinned.limits()[pk]
        acc, perm = _num(record.get("acceptable")), _num(record.get("permissible"))
        if acc != float(lim["acceptable"]) or perm != float(lim["permissible"]):
            add(
                "LIMIT_MISMATCH",
                f"record limits {record.get('acceptable')!r}/{record.get('permissible')!r} != pinned {lim['acceptable']}/{lim['permissible']}"
                + (" (arsenic permissible is 'No relaxation' = 0.01 since IS 10500:2012 Amendment No.1, 2015; 0.05 is the unamended 2012 value)"
                   if pk == "arsenic" and perm != float(lim["permissible"]) else ""),
            )
        if pv["number"] is not None:
            p = float(lim["permissible"])
            below = pv["number"] <= 0 if pk == "ecoli" else pv["number"] <= p
            if below:
                add("BELOW_LIMIT_BUT_LISTED", f"value {pv['number']} does not exceed pinned permissible {lim['permissible']} but the record is listed as contaminated")

    dt = parse_test_date(record.get("tested"))
    if dt is None:
        add("TEST_DATE_INVALID", f"test date {record.get('tested')!r} is not DD/MM/YYYY HH:MM:SS")
    elif dt.date() > datetime.strptime(snapshot_date, "%Y-%m-%d").date():
        add("TEST_DATE_INVALID", f"test date {record.get('tested')!r} is after the snapshot date {snapshot_date}")

    lab_raw = record.get("lab") or ""
    verbatim = lab_raw in lab_names
    normalized = norm_name(lab_raw) in {norm_name(n) for n in lab_names}
    lab_match = {"lab": lab_raw, "verbatim_match": verbatim, "normalized_match": normalized}
    if not normalized:
        warnings.append({"code": "LAB_NOT_IN_L10", "detail": f"original lab {lab_raw!r} not found in L10 lab list even after whitespace/case normalization"})

    return {"reasons": reasons, "warnings": warnings, "lab_match": lab_match, "param_key": pk, "parsed": pv}
