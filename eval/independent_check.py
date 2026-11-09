"""Independent re-check of eval/public_sample_30.csv.

Written separately from the jalsetu package (no imports from it) by the same solo builder,
so it is a second code path, NOT an external or field validation.
Reads only the raw snapshot CSVs and the published public sample, re-derives each field
with its own rules typed from IS 10500:2012 (as amended) and the L10 lab list, and reports
every mismatch. Usage: python eval/independent_check.py
"""
import csv, hashlib, json, re, sys, datetime, os

ROOT = os.environ.get("JALSETU_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "data", "snapshots", "2026-11-09")
PUB = os.path.join(ROOT, "eval", "public_sample_30.csv")
OUT_CSV = os.path.join(ROOT, "eval", "independent_check_30.csv")
OUT_JSON = os.path.join(ROOT, "eval", "results", "independent_check_30.json")

# Own limit table (permissible, unit) typed from IS 10500:2012 Tables 2, 3, 6 (Amend. No.1 2015 for arsenic)
LIMITS = {"Fluoride": (1.5, "mg/l"), "Nitrate": (45.0, "mg/l"),
          "Total arsenic": (0.01, "mg/l"), "Ecoil": (0.0, "cfu/100ml")}
# Own L10 token rules
LAB_TOKEN = {"Fluoride": r"\bfluoride\b", "Nitrate": r"\bnitrate\b",
             "Total arsenic": r"\barsenic\b", "Ecoil": r"\be\.\s?coli\b"}
# Expected advice ids per parameter (from 구성안_v4 §2.3)
ADVICE = {"Fluoride": "CHEM_1;CHEM_2;CHEM_3;CHEM_4;F_1;H_CHEM",
          "Nitrate": "CHEM_1;CHEM_2;CHEM_3;CHEM_4;N_1;H_CHEM;H_N1;H_N2",
          "Total arsenic": "CHEM_1;CHEM_2;CHEM_3;CHEM_4;AS_1;H_CHEM;H_AS",
          "Ecoil": "EC_1;EC_2;H_EC"}


def norm(s):
    return " ".join((s or "").split()).lower()


def parse_value(v):
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*\(([^)]*)\)\s*$", v or "")
    if not m:
        return None, None
    return float(m.group(1)), m.group(2).replace(" ", "").lower()


def main():
    raw = list(csv.DictReader(open(os.path.join(SNAP, "wq6_AP_2024-2025_samples.csv"), encoding="utf-8")))
    labs = list(csv.DictReader(open(os.path.join(SNAP, "wq_labs_AP_L10.csv"), encoding="utf-8")))
    pub = list(csv.DictReader(open(PUB, encoding="utf-8")))
    labs_by_name = {norm(l["name"]): l for l in labs}

    # 1) selection rule: sha256(sample_id) ascending, first 30 (records keyed by sample_id+param)
    keyed = sorted(raw, key=lambda r: (hashlib.sha256(r["sample_id"].encode()).hexdigest(), r["param"]))
    expected_sel = [(r["sample_id"], r["param"]) for r in keyed[:30]]
    got_sel = [(r["sample_id"], r["param"]) for r in pub]
    selection_ok = sorted(expected_sel) == sorted(got_sel)

    rows, mismatches = [], 0
    raw_idx = {(r["sample_id"], r["param"]): r for r in raw}
    for p in pub:
        k = (p["sample_id"], p["param"])
        r = raw_idx.get(k)
        checks = {}
        checks["raw_record_found"] = r is not None
        if r:
            checks["raw_fields_identical"] = all(p[c] == r[c] for c in r.keys())
        val, unit = parse_value(p["value"])
        lim, lim_unit = LIMITS.get(p["param"], (None, None))
        exceeds = (val is not None and lim is not None and unit == lim_unit and val > lim)
        checks["exceeds_matches"] = (str(exceeds) == p["exceeds"])
        if p["param"] != "Ecoil" and val is not None and lim:
            checks["ratio_matches"] = (p["ratio"] != "" and abs(round(val / lim, 2) - float(p["ratio"])) < 0.006)
        exp_status = "ready" if exceeds else "needs_review"
        checks["status_matches"] = (p["status"] == exp_status)
        lab = labs_by_name.get(norm(p["top_lab"]))
        checks["top_lab_in_L10"] = lab is not None
        if lab:
            checks["top_lab_tests_param"] = re.search(LAB_TOKEN[p["param"]], lab["parameters"].lower()) is not None
            in_district = norm(p["district"]) in norm(lab["name"]) or norm(p["district"]) in norm(lab["address"])
            checks["same_district_flag_matches"] = (str(in_district) == p["top_lab_same_district"])
        checks["advice_ids_match"] = (p["advice_ids"] == ADVICE.get(p["param"]))
        checks["fact_guard_pass"] = (p["fact_guard"] == "True")
        bad = [c for c, ok in checks.items() if not ok]
        mismatches += bool(bad)
        rows.append({"sample_id": p["sample_id"], "param": p["param"], "value": p["value"],
                     "independent_permissible": lim, "independent_exceeds": exceeds,
                     "published_status": p["status"], "published_top_lab": p["top_lab"],
                     "checks_passed": sum(checks.values()), "checks_total": len(checks),
                     "mismatches": ";".join(bad)})

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    summary = {"name": "independent re-check of public sample 30",
               "nature": "second code path by the same solo builder; not external, not field validation",
               "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "command": "python eval/independent_check.py",
               "selection_rule_reproduced": selection_ok,
               "rows": len(rows), "rows_with_any_mismatch": mismatches,
               "checks_total": sum(r["checks_total"] for r in rows),
               "checks_passed": sum(r["checks_passed"] for r in rows)}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(summary, open(OUT_JSON, "w"), indent=1)
    print(json.dumps(summary, indent=1))
    for r in rows:
        if r["mismatches"]:
            print("MISMATCH", r["sample_id"], r["param"], r["mismatches"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
