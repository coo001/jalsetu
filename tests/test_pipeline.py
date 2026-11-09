from collections import Counter

from jalsetu.pipeline import build_all, build_packet


def test_all_ready(snap):
    assert Counter((p["state"], p["status"]) for p in build_all(snap)) == Counter({("AP", "ready"): 283, ("BR", "ready"): 592})


def test_needs_review_has_no_advice(rec, snap):
    rec["value"] = "NA (mg/l)"
    p = build_packet(rec, snap)
    assert p["status"] == "needs_review" and p["household_advice"] == [] and p["officer_actions"] == [] and p["letter"] is None
    assert [r["code"] for r in p["reasons"]] == ["VALUE_NOT_NUMERIC"]


def test_arsenic_synthetic(rec, snap):
    rec.update(param="Total arsenic", acceptable="0.01", permissible="0.01", value="0.050 (mg/l)")
    p = build_packet(rec, snap)
    assert p["status"] == "ready" and p["labs_total"] == 3 and p["verdict"]["ratio"] == 5.0
    assert [a["id"] for a in p["household_advice"]] == ["H_CHEM", "H_AS"]
    assert not any("boil" in a["text"].lower() for a in p["officer_actions"] + p["household_advice"])


def test_no_candidate_lab(rec, snap):
    from jalsetu.lab_router import lab_tests
    snap.labs = [l for l in snap.labs if not lab_tests(l, "arsenic")]
    rec.update(param="Total arsenic", acceptable="0.01", permissible="0.01", value="0.050 (mg/l)")
    p = build_packet(rec, snap)
    assert p["status"] == "no_candidate_lab" and p["letter"] is None and p["labs"] == []
    assert "Contact the State Level laboratory" in p["lab_limit_note"]


def test_trace_order(rec, snap):
    tools = [t["tool"] for t in build_packet(rec, snap)["trace"]]
    assert tools == ["snapshot.load_record", "record_validator.validate", "is10500_check.verdict", "lab_router.route",
                     "advice.build", "draft_packet.draft", "fact_guard.check"]


def test_llm_fallback_without_network(rec, snap, monkeypatch):
    from jalsetu import draft_packet
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def boom(*a, **k):
        raise TimeoutError("no network in tests")
    monkeypatch.setattr(draft_packet, "_gemini_polish", boom)
    p = build_packet(rec, snap, use_llm=True)
    assert p["status"] == "ready" and p["letter"]["method"] == "template" and "TimeoutError" in p["letter"]["llm_note"]


def test_llm_bad_rewrite_rejected(rec, snap, monkeypatch):
    from jalsetu import draft_packet
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(draft_packet, "_gemini_polish", lambda text, key: text.replace(rec["sample_id"], "U000000S00000000"))
    p = build_packet(rec, snap, use_llm=True)
    assert p["letter"]["method"] == "template" and p["fact_guard"]["passed"]


def test_llm_good_rewrite_accepted(rec, snap, monkeypatch):
    from jalsetu import draft_packet
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(draft_packet, "_gemini_polish", lambda text, key: text.replace("Sir/Madam,", "Dear Sir or Madam,"))
    p = build_packet(rec, snap, use_llm=True)
    assert p["letter"]["method"] == "llm" and "Dear Sir or Madam" in p["letter"]["text"]
