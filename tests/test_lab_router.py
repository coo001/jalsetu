import random

from jalsetu.lab_router import LIMIT_NOTE, NO_LAB_NOTE, lab_tests, parameter_items, route


def lab(params, name="X Lab", group="DISTRICT LEVEL", acc="Yes", address=""):
    return {"sno": "1", "name": name, "group": group, "accredited": acc, "address": address, "parameters": params}


def test_parameter_items():
    assert parameter_items("1.Aluminum (As Al), 2.Chloride (as Cl), 10.E. coli") == ["Aluminum (As Al)", "Chloride (as Cl)", "E. coli"]


def test_tokens():
    assert lab_tests(lab("1.Total coliform, 2.pH"), "ecoli") is None
    assert lab_tests(lab("1.E. coli, 2.Total coliform"), "ecoli") == "E. coli"
    assert lab_tests(lab("1.Total Arsenic (As As)"), "arsenic") == "Total Arsenic (As As)"
    assert lab_tests(lab("1.Arsenic"), "arsenic") == "Arsenic"
    assert lab_tests(lab("1.Nitrite (as NO2)"), "nitrate") is None
    assert lab_tests(lab("1.Nitrate (as NO3)"), "nitrate") == "Nitrate (as NO3)"
    assert lab_tests(lab("1.Fluoride (as F)"), "fluoride") == "Fluoride (as F)"
    assert lab_tests(lab("1.Fluoride (as F)"), "unknown") is None


def test_ap_counts(snap):
    n = {k: route(k, "", snap.labs_for("AP"))["total"] for k in ("fluoride", "nitrate", "arsenic", "ecoli")}
    assert n == {"fluoride": 122, "nitrate": 119, "arsenic": 3, "ecoli": 114}


def test_ordering():
    labs = [
        lab("1.Fluoride", "Zeta WTP", "WTP Lab", "Yes"),
        lab("1.Fluoride", "Alpha Sub", "SUB DIVISIONAL LEVEL", "No"),
        lab("1.Fluoride", "Kurnool - District Level", "DISTRICT LEVEL", "No"),
        lab("1.Fluoride", "Beta State", "STATE LEVEL", "Yes"),
        lab("1.Fluoride", "Gamma Sub", "SUB DIVISIONAL LEVEL", "Yes", address="Main road, Kurnool"),
        lab("1.pH", "No Fluoride Lab", "STATE LEVEL", "Yes", address="Kurnool"),
    ]
    out = route("fluoride", "Kurnool", labs)
    names = [l["name"] for l in out["labs"]]
    assert names == ["Gamma Sub", "Kurnool - District Level", "Beta State", "Zeta WTP", "Alpha Sub"]
    assert out["labs"][0]["district_match_field"] == "address" and out["labs"][1]["district_match_field"] == "name"
    assert out["total"] == 5 and out["limit_note"] == LIMIT_NOTE
    random.Random(1).shuffle(labs)
    assert [l["name"] for l in route("fluoride", "Kurnool", labs)["labs"]] == names


def test_district_word_boundary():
    out = route("fluoride", "NTR", [lab("1.Fluoride", "CENTRAL Lab")])
    assert out["labs"][0]["same_district"] is False


def test_zero_candidates():
    out = route("arsenic", "Kurnool", [lab("1.Fluoride")])
    assert out["total"] == 0 and out["labs"] == [] and out["limit_note"] == NO_LAB_NOTE


def test_top5(snap):
    assert len(route("fluoride", "Kurnool", snap.labs_for("AP"))["labs"]) == 5
