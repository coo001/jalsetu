from jalsetu.fact_guard import check
from jalsetu.pipeline import build_packet, universe
from jalsetu import draft_packet


def facts_and_text(rec, snap):
    p = build_packet(rec, snap)
    return p, p["letter"]["text"]


def guard(p, text, snap):
    from jalsetu.units import parse_value
    f = draft_packet.facts_for(p["record"], p["verdict"], parse_value(p["record"]["value"]), p["labs"][0])
    return check(text, f, universe(snap))


def test_template_passes(rec, snap):
    p, t = facts_and_text(rec, snap)
    assert p["fact_guard"]["passed"], p["fact_guard"]


def test_wrong_value_rejected(rec, snap):
    p, t = facts_and_text(rec, snap)
    raw = rec["value"].split()[0]
    assert not guard(p, t.replace(f"Reported value: {raw}", "Reported value: 9.999"), snap)["passed"]


def test_value_replaced_with_allowed_number_rejected(rec, snap):
    p, t = facts_and_text(rec, snap)
    raw = rec["value"].split()[0]
    assert not guard(p, t.replace(f"Reported value: {raw}", "Reported value: 1.5"), snap)["passed"]


def test_number_format_normalized(rec, snap):
    p, t = facts_and_text(rec, snap)
    raw = rec["value"].split()[0]
    assert guard(p, t.replace(f"Reported value: {raw}", f"Reported value: {float(raw):g}"), snap)["passed"]


def test_wrong_sample_id(rec, snap):
    p, t = facts_and_text(rec, snap)
    sid = rec["sample_id"]
    bad = sid[:-1] + ("0" if sid[-1] != "0" else "1")
    assert not guard(p, t.replace(f"Sample ID: {sid}", f"Sample ID: {bad}"), snap)["passed"]


def test_wrong_lab(rec, snap):
    p, t = facts_and_text(rec, snap)
    other = next(l["name"] for l in snap.labs if l["name"] not in (p["labs"][0]["name"], rec["lab"]))
    assert not guard(p, t + f"\nCopy to: {other}", snap)["passed"]


def test_wrong_village(rec, snap):
    p, t = facts_and_text(rec, snap)
    other = next(r["village"] for r in snap.samples if r["village"] not in (rec["village"], rec["gp"], rec["block"]) and len(r["village"]) >= 5)
    assert not guard(p, t.replace(f"Village {rec['village']}", f"Village {other}"), snap)["passed"]


def test_extra_number(rec, snap):
    p, t = facts_and_text(rec, snap)
    assert not guard(p, t + "\nPlease reply within 7 days.", snap)["passed"]
