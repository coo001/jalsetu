import pytest

from jalsetu import advice, pinned


def ids(p):
    a = advice.build(p)
    return [x["id"] for x in a["officer_actions"]], [x["id"] for x in a["household_advice"]]


def test_mapping():
    assert ids("fluoride") == (["CHEM_1", "CHEM_2", "CHEM_3", "CHEM_4", "F_1"], ["H_CHEM"])
    assert ids("nitrate") == (["CHEM_1", "CHEM_2", "CHEM_3", "CHEM_4", "N_1"], ["H_CHEM", "H_N1", "H_N2"])
    assert ids("arsenic") == (["CHEM_1", "CHEM_2", "CHEM_3", "CHEM_4", "AS_1"], ["H_CHEM", "H_AS"])
    assert ids("ecoli") == (["EC_1", "EC_2"], ["H_EC"])


@pytest.mark.parametrize("p", ["fluoride", "arsenic", "nitrate"])
def test_no_boil_for_chemicals(p):
    a = advice.build(p)
    for x in a["officer_actions"] + a["household_advice"]:
        if "boil" in x["text"].lower():
            assert (p, x["id"]) == ("nitrate", "H_N2")


def test_every_line_sourced():
    srcs = pinned.sources()
    for line in pinned.table()["lines"]:
        assert line["source_ids"] and all(s in srcs for s in line["source_ids"]) and line["ref"]


def test_text_is_verbatim_from_table():
    table = {l["id"]: l["text"] for l in pinned.table()["lines"]}
    for p in pinned.mapping():
        a = advice.build(p)
        for x in a["officer_actions"] + a["household_advice"]:
            assert x["text"] == table[x["id"]]


def test_pinned_text_exact():
    t = {l["id"]: l["text"] for l in pinned.table()["lines"]}
    assert t["EC_2"] == "Take immediate investigative action to find the cause."
    assert t["H_N1"] == "Do not use this water to prepare infant formula."
    assert pinned.limits()["arsenic"]["permissible"] == 0.01
