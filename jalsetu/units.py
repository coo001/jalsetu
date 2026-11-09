"""Parse WQMIS value strings like '2.000 (mg/l)' or '50.000 (CFU/100 ml)'."""
import re

_VALUE_RE = re.compile(r"^\s*(?P<num>\S+?)\s*(?:\((?P<unit>[^)]*)\))?\s*$")
_NUM_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")

CANONICAL_UNITS = {
    "mg/l": "mg/l",
    "cfu/100ml": "CFU/100 ml",
}


def canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    key = re.sub(r"\s+", "", unit).lower()
    return CANONICAL_UNITS.get(key)


def parse_value(raw: str | None) -> dict:
    """Return {raw_number, number, unit_raw, unit, error}. error in {None, 'missing', 'not_numeric'}."""
    out = {"raw_number": None, "number": None, "unit_raw": None, "unit": None, "error": None}
    if raw is None or not str(raw).strip():
        out["error"] = "missing"
        return out
    m = _VALUE_RE.match(str(raw))
    if not m:
        out["error"] = "not_numeric"
        return out
    num, unit = m.group("num"), m.group("unit")
    out["unit_raw"] = unit.strip() if unit is not None and unit.strip() else None
    out["unit"] = canonical_unit(out["unit_raw"])
    if not _NUM_RE.match(num):
        out["error"] = "not_numeric"
        return out
    out["raw_number"] = num
    out["number"] = float(num)
    return out
