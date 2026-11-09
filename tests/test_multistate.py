from jalsetu import fact_guard
from jalsetu.lab_router import lab_tests
from jalsetu.pipeline import build_packet, universe
from jalsetu.record_validator import EXTREME_UI_TEXT


def br_rec(snap):
    return dict(next(r for r in snap.samples if r["state"] == "BR"))


def test_br_record_routed_to_br_labs_only(snap):
    rec = br_rec(snap)
    p = build_packet(rec, snap)
    br_names = {" ".join(l["name"].split()) for l in snap.labs_for("BR") if lab_tests(l, "arsenic")}
    ap_names = {" ".join(l["name"].split()) for l in snap.labs_for("AP")}
    assert p["status"] == "ready" and p["state"] == "BR"
    assert p["labs_total"] == len(br_names)
    assert {l["name"] for l in p["labs"]} <= br_names
    assert not ({l["name"] for l in p["labs"]} & (ap_names - br_names))
    assert p["lab_limit_note"].startswith("Candidate labs are listed only because this state's WQMIS lab list")


def test_br_routing_ignores_br_labs_without_arsenic(snap):
    rec = br_rec(snap)
    keep = {id(l) for l in snap.labs_for("BR")[:5]}
    for l in snap.labs:
        if l["state"] == "BR" and id(l) not in keep:
            l["parameters"] = "1.pH, 2.Chloride (as Cl)"
    p = build_packet(rec, snap)
    assert p["labs_total"] == 5
    assert all("arsenic" in l["l10_item"].lower() for l in p["labs"])


def test_br_record_without_br_labs_does_not_use_ap(snap):
    rec = br_rec(snap)
    snap.labs = [l for l in snap.labs if l["state"] != "BR"]
    p = build_packet(rec, snap)
    assert p["status"] == "no_candidate_lab" and p["labs"] == []


def test_ap_record_still_uses_ap_labs(rec, snap):
    rec.update(param="Total arsenic", acceptable="0.01", permissible="0.01", value="0.050 (mg/l)")
    assert build_packet(rec, snap)["labs_total"] == 3


def test_value_extreme_warning_letter_and_guard(snap):
    rec = dict(br_rec(snap), value="228.000 (mg/l)")
    p = build_packet(rec, snap)
    assert p["status"] == "ready"  # warning only
    assert [w["code"] for w in p["warnings"]] == ["VALUE_EXTREME"] and EXTREME_UI_TEXT in p["warnings"][0]["detail"]
    assert p["verdict"]["exceeds"] is True and p["verdict"]["ratio"] == 22800.0
    assert "Please confirm the reported value and unit." in p["letter"]["text"]
    assert p["fact_guard"]["passed"]


def test_value_extreme_boundary(snap):
    base = br_rec(snap)
    assert [w["code"] for w in build_packet(dict(base, value="1.000 (mg/l)"), snap)["warnings"]] == ["VALUE_EXTREME"]
    p = build_packet(dict(base, value="0.999 (mg/l)"), snap)
    assert p["warnings"] == [] and "Please confirm the reported value" not in p["letter"]["text"]


def test_value_extreme_not_for_ecoli(rec, snap):
    ec = next(r for r in snap.samples if r["state"] == "AP" and r["param"].lower().startswith("e"))
    p = build_packet(dict(ec, value="5000.000 (CFU/100 ml)"), snap)
    assert not any(w["code"] == "VALUE_EXTREME" for w in p["warnings"])


def test_guard_rejects_dropped_confirmation_line(snap):
    rec = dict(br_rec(snap), value="228.000 (mg/l)")
    p = build_packet(rec, snap)
    from jalsetu.draft_packet import facts_for
    from jalsetu.units import parse_value
    f = facts_for(p["record"], p["verdict"], parse_value(rec["value"]), p["labs"][0], value_extreme=True)
    bad = p["letter"]["text"].replace("Please confirm the reported value and unit.\n", "")
    assert not fact_guard.check(bad, f, universe(snap))["passed"]


def test_digits_in_place_names_allowed(snap):
    p = next(build_packet(r, snap) for r in snap.samples if r["sample_id"] == "U735548S22966995")
    assert p["record"]["village"] == "Rani 3" and p["status"] == "ready" and p["fact_guard"]["passed"]
