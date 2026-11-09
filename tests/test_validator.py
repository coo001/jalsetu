import pytest

from jalsetu.record_validator import validate


def run(rec, snap, counts=None):
    return validate(rec, counts if counts is not None else snap.key_counts, {l["name"] for l in snap.labs}, snap.date)


def codes(res):
    return {r["code"] for r in res["reasons"]}


def test_all_originals_clean(snap):
    for r in snap.samples:
        assert run(r, snap)["reasons"] == [], r["sample_id"]


@pytest.mark.parametrize("field,value,code", [
    ("value", "", "VALUE_MISSING"),
    ("value", "NA (mg/l)", "VALUE_NOT_NUMERIC"),
    ("value", "2.000", "UNIT_MISSING"),
    ("value", "2.000 (ppm)", "UNIT_MISMATCH"),
    ("param", "Iron", "UNKNOWN_PARAM"),
    ("permissible", "1.0", "LIMIT_MISMATCH"),
    ("acceptable", "1.5", "LIMIT_MISMATCH"),
    ("value", "1.500 (mg/l)", "BELOW_LIMIT_BUT_LISTED"),
    ("sample_id", "  ", "SAMPLE_ID_MISSING"),
    ("tested", "31/02/2024 10:00:00", "TEST_DATE_INVALID"),
    ("tested", "2024-11-13 10:00", "TEST_DATE_INVALID"),
    ("tested", "01/01/2030 10:00:00", "TEST_DATE_INVALID"),
])
def test_reason(rec, snap, field, value, code):
    rec[field] = value
    assert code in codes(run(rec, snap))


def test_duplicate_same_param(rec, snap):
    snap.samples.append(dict(rec))
    snap.recount()
    assert "SAMPLE_ID_DUPLICATE" in codes(run(rec, snap))


def test_same_sample_two_params_is_not_duplicate(snap):
    ids = [r["sample_id"] for r in snap.samples]
    multi = [r for r in snap.samples if ids.count(r["sample_id"]) > 1]
    assert multi and all("SAMPLE_ID_DUPLICATE" not in codes(run(r, snap)) for r in multi)


def test_arsenic_record_must_use_001(rec, snap):
    rec.update(param="Total arsenic", acceptable="0.01", permissible="0.05", value="0.030 (mg/l)")
    assert codes(run(rec, snap)) == {"LIMIT_MISMATCH"}
    rec["permissible"] = "0.01"
    assert codes(run(rec, snap)) == set()


def test_ecoli_zero_is_below(snap):
    r = dict(next(r for r in snap.samples if r["param"] == "Ecoil"))
    r["value"] = "0.000 (CFU/100 ml)"
    assert "BELOW_LIMIT_BUT_LISTED" in codes(run(r, snap))


def test_lab_warning_only(rec, snap):
    rec["lab"] = "Some Unknown Laboratory"
    res = run(rec, snap)
    assert res["reasons"] == [] and [w["code"] for w in res["warnings"]] == ["LAB_NOT_IN_L10"]


def test_lab_whitespace_normalized(snap):
    r = next(r for r in snap.samples if "  " in r["lab"])
    m = run(r, snap)["lab_match"]
    assert m["verbatim_match"] is False and m["normalized_match"] is True
