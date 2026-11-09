"""Re-test request letter: deterministic template; optional LLM may only reword it."""
import json
import os
import urllib.request

from . import fact_guard

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RETEST_CHEM = (
    "all basic and area-specific chemical parameters and bacteriological parameters "
    "(per JJM-HB 2.6), including {param}"
)
RETEST_EC = "E. coli and the other bacteriological parameters (per JJM-HB 2.6)"


def _ws(s):
    return " ".join((s or "").split())


def facts_for(record: dict, verdict: dict, parsed: dict, target_lab: dict) -> dict:
    return {
        "sample_id": record["sample_id"].strip(),
        "village": _ws(record["village"]),
        "gp": _ws(record["gp"]),
        "block": _ws(record["block"]),
        "district": _ws(record["district"]),
        "source": _ws(record["source"]),
        "param": verdict["param"],
        "param_display": verdict["param_display"],
        "value_text": parsed["raw_number"],
        "unit": verdict["unit"],
        "acceptable_text": f"{verdict['acceptable']:g}",
        "permissible_text": f"{verdict['permissible']:g}",
        "ratio_text": f"{verdict['ratio']:.2f}" if verdict["ratio"] is not None else None,
        "limit_ref": verdict["limit_ref"],
        "orig_lab": _ws(record["lab"]),
        "target_lab": target_lab["name"],
        "target_address": target_lab["address"],
        "tested": record["tested"].strip(),
    }


def template_letter(f: dict) -> str:
    if f["param"] == "ecoli":
        limit_line = f"Permissible limit: {f['permissible_text']} {f['unit']} (not detectable in any 100 ml; {f['limit_ref']})"
        ratio_line = "Ratio to permissible limit: not applicable (limit is zero; see reported count above)"
        retest = RETEST_EC
    else:
        limit_line = f"Permissible limit: {f['permissible_text']} {f['unit']} ({f['limit_ref']})"
        ratio_line = f"Ratio to permissible limit: {f['ratio_text']} times"
        retest = RETEST_CHEM.format(param=f["param_display"])
    return "\n".join(
        [
            f"To: The Officer In-charge, {f['target_lab']}",
            f"Address (as listed in WQMIS L10): {f['target_address']}",
            "",
            f"Subject: Request to re-test drinking-water sample {f['sample_id']} ({f['param_display']})",
            "",
            "Sir/Madam,",
            "",
            "The sample below is recorded in WQMIS as exceeding the IS 10500:2012 drinking-water limit. "
            "We request a re-test before any decision on restoring this source.",
            "",
            f"Sample ID: {f['sample_id']}",
            f"Location: Village {f['village']}, Gram Panchayat {f['gp']}, Block {f['block']}, District {f['district']}",
            f"Source: {f['source']}",
            f"Parameter: {f['param_display']}",
            f"Reported value: {f['value_text']} {f['unit']}",
            limit_line,
            ratio_line,
            f"Original testing laboratory: {f['orig_lab']}",
            f"Original test date: {f['tested']}",
            "",
            f"Requested re-test parameters: {retest}.",
            "",
            "Please confirm that your laboratory can accept this sample, and the expected turnaround time, "
            "before the sample is sent.",
            "",
            "Yours faithfully,",
            "(Name, designation and signature of the responsible officer)",
            "",
            "Drafted by JalSetu decision-support software from the WQMIS record. "
            "The responsible officer must check every detail before signing.",
        ]
    )


def _gemini_polish(text: str, api_key: str, timeout: float = 15.0) -> str:
    prompt = (
        "Improve the wording of this official letter for clarity and politeness. "
        "Do NOT change, add or remove any number, date, sample ID, laboratory name, place name or the source text. "
        "Keep every line that starts with a label (e.g. 'Sample ID:') exactly as written. Return only the letter.\n\n"
        + text
    )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(
        GEMINI_URL.format(model=GEMINI_MODEL),
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def draft(record: dict, verdict: dict, parsed: dict, target_lab: dict, universe: dict, use_llm: bool | None = None) -> dict:
    facts = facts_for(record, verdict, parsed, target_lab)
    text = template_letter(facts)
    guard = fact_guard.check(text, facts, universe)
    out = {"text": text, "method": "template", "llm_note": "no GEMINI_API_KEY set; template used", "facts": facts, "fact_guard": guard}
    api_key = os.environ.get("GEMINI_API_KEY")
    if use_llm is None:
        use_llm = bool(api_key)
    if not (use_llm and api_key):
        return out
    try:
        polished = _gemini_polish(text, api_key)
    except Exception as e:  # any network/format error -> template
        out["llm_note"] = f"LLM call failed ({type(e).__name__}); template used"
        return out
    pg = fact_guard.check(polished, facts, universe)
    if not pg["passed"]:
        out["llm_note"] = "LLM wording rejected by fact_guard; template used"
        out["llm_rejected_reasons"] = pg["reasons"]
        return out
    out.update(text=polished, method="llm", llm_note=f"wording polished by {GEMINI_MODEL}; facts verified by fact_guard", fact_guard=pg)
    return out
