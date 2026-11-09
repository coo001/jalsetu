"""E5: limit boundaries and unit parsing (eval/run_eval.py runs this file and reports the pass count)."""
import pytest

from jalsetu.is10500_check import verdict
from jalsetu.units import canonical_unit, parse_value


@pytest.mark.parametrize("key,value,exceeds", [
    ("fluoride", 1.5, False), ("fluoride", 1.51, True), ("fluoride", 1.0, False),
    ("nitrate", 45, False), ("nitrate", 45.1, True),
    ("arsenic", 0.01, False), ("arsenic", 0.011, True),
    ("ecoli", 0, False), ("ecoli", 1, True),
])
def test_limit_boundaries(key, value, exceeds):
    unit = "CFU/100 ml" if key == "ecoli" else "mg/l"
    assert verdict(key, value, unit)["exceeds"] is exceeds


def test_ratio():
    assert verdict("fluoride", 2.0, "mg/l")["ratio"] == 1.33
    assert verdict("nitrate", 90, "mg/l")["ratio"] == 2.0
    assert verdict("ecoli", 50, "CFU/100 ml")["ratio"] is None


@pytest.mark.parametrize("raw,unit", [
    ("mg/l", "mg/l"), ("mg/L", "mg/l"), ("MG/L", "mg/l"), (" mg / l ", "mg/l"),
    ("CFU/100 ml", "CFU/100 ml"), ("CFU/100ml", "CFU/100 ml"), ("cfu/100 ML", "CFU/100 ml"),
    ("ppm", None), ("MPN/100 ml", None), ("µg/l", None),
])
def test_unit_variants(raw, unit):
    assert canonical_unit(raw) == unit


@pytest.mark.parametrize("raw,num,unit,err", [
    ("2.000 (mg/l)", 2.0, "mg/l", None),
    ("50.000 (CFU/100 ml)", 50.0, "CFU/100 ml", None),
    ("0.011 (MG/L)", 0.011, "mg/l", None),
    ("2.000", 2.0, None, None),
    ("", None, None, "missing"),
    ("NA (mg/l)", None, "mg/l", "not_numeric"),
    ("<0.5 (mg/l)", None, "mg/l", "not_numeric"),
    ("1,5 (mg/l)", None, "mg/l", "not_numeric"),
])
def test_parse_value(raw, num, unit, err):
    p = parse_value(raw)
    assert (p["number"], p["unit"], p["error"]) == (num, unit, err)
