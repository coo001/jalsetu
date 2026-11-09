"""Reject a letter if any number, sample id, lab name or village differs from the source record."""
import re

# Fixed phrases of the template whose digits are not record facts.
CONSTANT_PHRASES = ["IS 10500:2012", "WQMIS L10", "JJM-HB 2.6", "CFU/100 ml", "not detectable in any 100 ml"]

SAMPLE_ID_RE = re.compile(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,}\b")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _ws(s: str | None) -> str:
    return " ".join((s or "").split())


def _remove(text: str, phrases) -> str:
    # longest first so a phrase contained in a longer one does not leave fragments
    for p in sorted({_ws(p) for p in phrases if p}, key=len, reverse=True):
        text = re.sub(re.escape(p), " ", text, flags=re.I)
    return text


def _word_in(name: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", text.lower()) is not None


def check(letter: str, facts: dict, universe: dict) -> dict:
    """facts: sample_id, village, gp, block, district, source, target_lab, target_address, orig_lab,
    tested, value_text, permissible_text, acceptable_text, ratio_text (or None), limit_ref.
    universe: {'lab_names': [...], 'villages': [...]} from the snapshot."""
    text = _ws(letter)
    reasons = []

    # 1. required facts present, verbatim
    for k in ("sample_id", "tested"):
        if facts[k] not in text:
            reasons.append(f"missing {k} {facts[k]!r}")
    for k in ("village", "target_lab", "orig_lab"):
        if _ws(facts[k]).lower() not in text.lower():
            reasons.append(f"missing {k} {facts[k]!r}")

    # 2. every sample-id-like token must be the record's sample id
    allowed_strings = [facts[k] for k in ("source", "target_lab", "target_address", "orig_lab", "limit_ref")] + CONSTANT_PHRASES
    for tok in set(SAMPLE_ID_RE.findall(_remove(text, allowed_strings))):
        if tok != facts["sample_id"]:
            reasons.append(f"unknown sample id {tok!r}")

    # 3. no other lab names
    allowed_labs = {_ws(facts["target_lab"]).lower(), _ws(facts["orig_lab"]).lower()}
    no_labs = _remove(text, [facts["target_lab"], facts["orig_lab"]])
    for name in universe.get("lab_names", []):
        n = _ws(name)
        if n.lower() not in allowed_labs and len(n) >= 8 and n.lower() in no_labs.lower():
            reasons.append(f"unexpected lab name {n!r}")

    # 4. no other villages
    places = {_ws(facts[k]).lower() for k in ("village", "gp", "block", "district")}
    stripped = _remove(text, allowed_strings + [facts[k] for k in ("village", "gp", "block", "district")])
    for v in set(universe.get("villages", [])):
        v = _ws(v)
        if len(v) >= 5 and v.lower() not in places and _word_in(v, stripped):
            reasons.append(f"unexpected village {v!r}")

    # 5. every remaining number must equal a record number (after float normalization)
    numbers_body = _remove(text, allowed_strings + [facts["sample_id"], facts["tested"]])
    present_numbers = {float(m) for m in NUMBER_RE.findall(numbers_body)}
    allowed_numbers = {float(facts["value_text"]), float(facts["permissible_text"]), float(facts["acceptable_text"])}
    if facts.get("ratio_text"):
        allowed_numbers.add(float(facts["ratio_text"]))
    for k in ("value_text", "permissible_text") + (("ratio_text",) if facts.get("ratio_text") else ()):
        if float(facts[k]) not in present_numbers:
            reasons.append(f"missing number {k} {facts[k]}")
    for m in NUMBER_RE.findall(numbers_body):
        if float(m) not in allowed_numbers:
            reasons.append(f"unexpected number {m}")

    return {"passed": not reasons, "reasons": sorted(set(reasons))}
