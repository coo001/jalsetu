"""build_packet(record, snapshot): the whole deterministic decision flow, with a trace."""
from . import advice, draft_packet, lab_router
from .is10500_check import verdict as check_verdict
from .record_validator import validate
from .snapshot import Snapshot, record_id


def universe(snapshot: Snapshot) -> dict:
    return {
        "lab_names": [lab["name"] for lab in snapshot.labs],
        "villages": [r["village"] for r in snapshot.samples if r.get("village")],
    }


def build_packet(record: dict, snapshot: Snapshot, use_llm: bool | None = False) -> dict:
    trace = []

    def step(tool, inp, out):
        trace.append({"step": len(trace) + 1, "tool": tool, "input": inp, "output": out})

    rid = record_id(record)
    packet = {
        "record_id": rid,
        "sample_id": (record.get("sample_id") or "").strip(),
        "record": dict(record),
        "status": None,
        "reasons": [],
        "warnings": [],
        "verdict": None,
        "labs": [],
        "labs_total": 0,
        "lab_limit_note": None,
        "officer_actions": [],
        "household_advice": [],
        "letter": None,
        "fact_guard": None,
        "trace": trace,
    }
    step("snapshot.load_record", {"record_id": rid, "snapshot": snapshot.date}, {"param": record.get("param"), "value": record.get("value")})

    v = validate(record, snapshot.key_counts, {lab["name"] for lab in snapshot.labs}, snapshot.date)
    packet["reasons"], packet["warnings"], packet["lab_match"] = v["reasons"], v["warnings"], v["lab_match"]
    step(
        "record_validator.validate",
        {"fields": ["param", "value", "acceptable", "permissible", "sample_id", "tested", "lab"]},
        {"reasons": [r["code"] for r in v["reasons"]], "warnings": [w["code"] for w in v["warnings"]]},
    )

    pk, pv = v["param_key"], v["parsed"]
    if pk is not None and pv["number"] is not None and pv["unit"] is not None:
        packet["verdict"] = check_verdict(pk, pv["number"], pv["unit"])
        step("is10500_check.verdict", {"param": pk, "value": pv["number"], "unit": pv["unit"]},
             {k: packet["verdict"][k] for k in ("exceeds", "permissible", "ratio", "limit_ref")})

    if v["reasons"]:
        packet["status"] = "needs_review"
        step("pipeline.stop", {"reason_count": len(v["reasons"])}, {"status": "needs_review", "advice": "withheld", "letter": "withheld"})
        return packet

    routed = lab_router.route(pk, record.get("district", ""), snapshot.labs, record.get("lab", ""))
    packet["labs"], packet["labs_total"], packet["lab_limit_note"] = routed["labs"], routed["total"], routed["limit_note"]
    step("lab_router.route", {"param": pk, "district": record.get("district"), "l10_labs": len(snapshot.labs)},
         {"candidates": routed["total"], "same_district": routed["same_district_count"], "top": [lab["name"] for lab in routed["labs"]]})
    if routed["total"] == 0:
        packet["status"] = "no_candidate_lab"
        step("pipeline.stop", {}, {"status": "no_candidate_lab", "letter": "withheld"})
        return packet

    adv = advice.build(pk)
    packet["officer_actions"], packet["household_advice"] = adv["officer_actions"], adv["household_advice"]
    step("advice.build", {"param": pk}, {"officer": [a["id"] for a in adv["officer_actions"]], "household": [a["id"] for a in adv["household_advice"]]})

    letter = draft_packet.draft(record, packet["verdict"], pv, routed["labs"][0], universe(snapshot), use_llm=use_llm)
    packet["letter"] = {k: letter[k] for k in ("text", "method", "llm_note")}
    packet["fact_guard"] = letter["fact_guard"]
    step("draft_packet.draft", {"to": routed["labs"][0]["name"], "use_llm": bool(use_llm)}, {"method": letter["method"], "chars": len(letter["text"])})
    step("fact_guard.check", {"facts": sorted(k for k, val in letter["facts"].items() if val is not None)}, letter["fact_guard"])

    packet["status"] = "ready" if letter["fact_guard"]["passed"] else "needs_review"
    if not letter["fact_guard"]["passed"]:  # never ship a letter that failed the guard
        packet["reasons"].append({"code": "LETTER_FACT_GUARD_FAILED", "detail": "; ".join(letter["fact_guard"]["reasons"])})
        packet["household_advice"], packet["officer_actions"], packet["letter"] = [], [], None
    return packet


def build_all(snapshot: Snapshot) -> list[dict]:
    return [build_packet(r, snapshot) for r in snapshot.samples]
