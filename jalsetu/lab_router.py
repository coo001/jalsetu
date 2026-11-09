"""Candidate re-test labs from the state's L10 lab list (capability as reported, nothing more)."""
import re

LIMIT_NOTE = (
    "Candidate labs are listed only because the state's WQMIS lab list (L10, snapshot 2026-11-09) "
    "says they test this parameter. Current availability, accreditation validity, cost, transport "
    "and turnaround time were NOT checked. Confirm with the lab before sending a sample."
)
NO_LAB_NOTE = "No lab in this state's L10 list tests this parameter. Contact the State Level laboratory."

# Each pattern must match the start of one L10 parameter item (after its "N." prefix is removed).
# 'Total coliform' must NOT count as E. coli; 'Nitrite' must NOT count as Nitrate.
PARAM_PATTERNS = {
    "fluoride": re.compile(r"^fluoride\b", re.I),
    "nitrate": re.compile(r"^nitrate\b", re.I),
    "arsenic": re.compile(r"^(total\s+)?arsenic\b", re.I),
    "ecoli": re.compile(r"^(e\.?\s*coli|escherichia\s+coli)\b", re.I),
}

GROUP_ORDER = ["STATE LEVEL", "DISTRICT LEVEL", "SUB DIVISIONAL LEVEL", "WTP LAB"]


def parameter_items(params: str) -> list[str]:
    """'1.Aluminum (As Al), 2.Chloride (as Cl)' -> ['Aluminum (As Al)', 'Chloride (as Cl)']"""
    parts = re.split(r",\s*(?=\d+\.)", params or "")
    return [re.sub(r"^\d+\.\s*", "", p).strip() for p in parts if p.strip()]


def lab_tests(lab: dict, param_key: str) -> str | None:
    """Return the L10 item text that lists this parameter, or None."""
    pat = PARAM_PATTERNS.get(param_key)
    if pat is None:
        return None
    for item in parameter_items(lab.get("parameters", "")):
        if pat.search(item):
            return item
    return None


def _district_hit(district: str, lab: dict) -> str | None:
    d = " ".join((district or "").split())
    if not d:
        return None
    pat = re.compile(r"(?<![a-z0-9])" + re.escape(d.lower()) + r"(?![a-z0-9])")
    for field in ("name", "address"):
        if pat.search(" ".join((lab.get(field) or "").split()).lower()):
            return field
    return None


def _group_rank(group: str) -> int:
    g = " ".join((group or "").split()).upper()
    return GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER)


def route(param_key: str, district: str, labs: list[dict], original_lab: str = "", top_n: int = 5) -> dict:
    orig = " ".join((original_lab or "").split()).lower()
    cands = []
    for lab in labs:
        item = lab_tests(lab, param_key)
        if item is None:
            continue
        hit = _district_hit(district, lab)
        accredited = (lab.get("accredited") or "").strip().lower() == "yes"
        name = " ".join((lab.get("name") or "").split())
        basis = [f"L10 lists '{item}'"]
        basis.append(f"district '{district}' appears in lab {hit}" if hit else "district name not found in lab name/address")
        basis.append("accredited: Yes (as reported by L10)" if accredited else f"accredited: {lab.get('accredited') or 'not stated'} (as reported by L10)")
        basis.append(f"group: {lab.get('group')}")
        is_orig = name.lower() == orig
        if is_orig:
            basis.append("this is the lab that did the original test")
        cands.append(
            {
                "name": name,
                "group": lab.get("group"),
                "address": " ".join((lab.get("address") or "").split()),
                "accredited": lab.get("accredited"),
                "same_district": bool(hit),
                "district_match_field": hit,
                "is_original_lab": is_orig,
                "l10_item": item,
                "sno": lab.get("sno"),
                "basis": basis,
                "_key": (0 if hit else 1, 0 if accredited else 1, _group_rank(lab.get("group")), name.lower(), str(lab.get("sno"))),
            }
        )
    cands.sort(key=lambda c: c["_key"])
    for c in cands:
        del c["_key"]
    return {
        "total": len(cands),
        "labs": cands[:top_n],
        "same_district_count": sum(c["same_district"] for c in cands),
        "limit_note": LIMIT_NOTE if cands else NO_LAB_NOTE,
    }
