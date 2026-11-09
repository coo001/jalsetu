"""Reproducibility and safety checks E1-E7 on the pinned snapshot. Not field impact.

Usage: python eval/run_eval.py   (or `make eval`)
"""
import copy
import csv
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jalsetu import fact_guard, pinned, snapshot  # noqa: E402
from jalsetu.draft_packet import facts_for  # noqa: E402
from jalsetu.is10500_check import verdict  # noqa: E402
from jalsetu.lab_router import route  # noqa: E402
from jalsetu.pipeline import build_packet, universe  # noqa: E402
from jalsetu.record_validator import REASON_CODES, norm_name, validate  # noqa: E402
from jalsetu.units import parse_value  # noqa: E402

SEED = 20261109
RESULTS = ROOT / "eval" / "results"
# Independent (plain substring) check of L10 capability, deliberately not reusing lab_router's regexes.
L10_TOKENS = {"fluoride": "fluoride (as f)", "nitrate": "nitrate (as no3)", "arsenic": "arsenic", "ecoli": "e. coli"}


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return "uncommitted"
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return f"uncommitted (working tree differs from {sha[:12]})" if dirty else sha


def fresh(snap: snapshot.Snapshot) -> snapshot.Snapshot:
    s = copy.copy(snap)
    s.samples = [dict(r) for r in snap.samples]
    s.labs = [dict(lab) for lab in snap.labs]
    s.recount()
    return s


def row(id_, name, target, measured, passed, note=""):
    return {"id": id_, "name": name, "target": target, "measured": measured, "passed": bool(passed), "note": note}


# ---------------- E1
def e1(snap, packets):
    numeric, exceeds = 0, 0
    for r in snap.samples:
        pk, pv = pinned.param_key(r["param"]), parse_value(r["value"])
        if pk and pv["number"] is not None and pv["unit"]:
            numeric += 1
            exceeds += verdict(pk, pv["number"], pv["unit"])["exceeds"]
    d = {"label": "reproduction, not independent accuracy", "records": len(snap.samples), "numeric": numeric, "exceeds_by_our_rule": exceeds,
         "by_param": dict(Counter(r["param"] for r in snap.samples))}
    return d, [row("E1", "Government verdict reproduction (reproduction, not independent accuracy)",
                   "all records with numeric values exceed by our rule", f"{exceeds}/{numeric} numeric records exceed (of {len(snap.samples)} records)",
                   exceeds == numeric)]


# ---------------- E2
def e2(snap, packets):
    by_name = {norm_name(lab["name"]): lab for lab in snap.labs}
    ready = [p for p in packets if p["status"] == "ready"]
    checked = unsuitable = 0
    for p in ready:
        tok = L10_TOKENS[p["verdict"]["param"]]
        for lab in p["labs"]:
            checked += 1
            if tok not in by_name[norm_name(lab["name"])]["parameters"].lower():
                unsuitable += 1
    hit = sum(any(lab["same_district"] for lab in p["labs"]) for p in ready)
    top_hit = sum(p["labs"][0]["same_district"] for p in ready)

    base = snap.samples[0]
    s = fresh(snap)
    ars = dict(base, param="Total arsenic", acceptable="0.01", permissible="0.01", value="0.050 (mg/l)")
    pa = build_packet(ars, s)
    s0 = fresh(snap)
    s0.labs = [lab for lab in s0.labs if "arsenic" not in lab["parameters"].lower()]
    pz = build_packet(ars, s0)

    rnd = random.Random(SEED)
    unstable = 0
    for p in ready:
        want = [lab["name"] for lab in p["labs"]]
        for _ in range(3):
            labs = list(snap.labs)
            rnd.shuffle(labs)
            if [lab["name"] for lab in route(p["verdict"]["param"], p["record"]["district"], labs, p["record"]["lab"])["labs"]] != want:
                unstable += 1
                break

    raw_names = {lab["name"] for lab in snap.labs}
    norm_names = {norm_name(n) for n in raw_names}
    sample_labs = Counter(r["lab"] for r in snap.samples)
    before = [n for n in sample_labs if n not in raw_names]
    after = [n for n in sample_labs if norm_name(n) not in norm_names]
    d = {
        "ready_packets": len(ready), "candidate_labs_checked": checked, "unsuitable": unsuitable,
        "packets_with_same_district_candidate": hit, "packets_without_same_district_candidate": len(ready) - hit,
        "packets_top_lab_same_district": top_hit,
        "synthetic_arsenic": {"status": pa["status"], "labs_total": pa["labs_total"], "labs": [lab["name"] for lab in pa["labs"]]},
        "synthetic_zero_lab": {"status": pz["status"], "letter": pz["letter"], "note": pz["lab_limit_note"],
                               "how": "arsenic record routed against AP L10 with the 3 arsenic-capable labs removed"},
        "tie_order_unstable_packets": unstable, "shuffles_per_packet": 3,
        "sample_lab_names_distinct": len(sample_labs),
        "not_in_l10_before_normalization": {"names": len(before), "records": sum(sample_labs[n] for n in before), "list": before},
        "not_in_l10_after_normalization": {"names": len(after), "records": sum(sample_labs[n] for n in after), "list": after},
    }
    rows = [
        row("E2a", "Candidate labs whose L10 list lacks the parameter", "0", f"{unsuitable} of {checked} candidate slots ({len(ready)} ready packets)", unsuitable == 0),
        row("E2b", "Ready packets with a same-district candidate", "report", f"{hit} with / {len(ready) - hit} without (top lab same-district: {top_hit})", True,
            "same-district = district name appears in L10 lab name or address"),
        row("E2c", "Synthetic arsenic case on AP L10", "ready, 3 candidate labs", f"{pa['status']}, {pa['labs_total']} labs", pa["status"] == "ready" and pa["labs_total"] == 3),
        row("E2d", "Synthetic parameter with zero labs", "no_candidate_lab, no letter", f"{pz['status']}, letter={'none' if pz['letter'] is None else 'present'}",
            pz["status"] == "no_candidate_lab" and pz["letter"] is None),
        row("E2e", "Lab order stable under input shuffles", "0 unstable", f"{unstable} unstable of {len(ready)}", unstable == 0),
        row("E2f", "Sample lab names not in L10", "report", f"before normalization {len(before)}/{len(sample_labs)} names ({d['not_in_l10_before_normalization']['records']} records); after {len(after)}/{len(sample_labs)}",
            True, "whitespace/case normalization"),
    ]
    return d, rows


# ---------------- E3
def _mutations(r, kind, i):
    pk = pinned.param_key(r["param"])
    lim = pinned.limits()[pk]
    num = r["value"].split()[0]
    unit = lim["unit"]
    if kind == "VALUE_MISSING":
        return [{"value": ""}, {"value": "   "}][i % 2]
    if kind == "VALUE_NOT_NUMERIC":
        return {"value": [f"NA ({unit})", f"<{num} ({unit})", f"{num.replace('.', ',')} ({unit})", f"BDL ({unit})", f"{num}a ({unit})"][i % 5]}
    if kind == "UNIT_MISSING":
        return {"value": [num, f"{num} ()"][i % 2]}
    if kind == "UNIT_MISMATCH":
        bad = ["MPN/100 ml", "CFU/ml"] if pk == "ecoli" else ["ppm", "µg/l", "mg/kg"]
        return {"value": f"{num} ({bad[i % len(bad)]})"}
    if kind == "UNKNOWN_PARAM":
        return {"param": ["Iron", "Chloride", "Total coliform", "Fluorine", "TDS", "Nitrite"][i % 6]}
    if kind == "LIMIT_MISMATCH":
        p = float(lim["permissible"])
        return [{"permissible": f"{p * 2 + 1:g}"}, {"acceptable": f"{float(lim['acceptable']) + 0.5:g}"}, {"permissible": "0.05" if pk != "ecoli" else "10"}][i % 3]
    if kind == "BELOW_LIMIT_BUT_LISTED":
        if pk == "ecoli":
            return {"value": f"0.000 ({unit})"}
        p = float(lim["permissible"])
        return {"value": f"{[p, p * 0.5, 0.0][i % 3]:.3f} ({unit})"}
    if kind == "SAMPLE_ID_MISSING":
        return {"sample_id": ["", "  "][i % 2]}
    if kind == "TEST_DATE_INVALID":
        return {"tested": ["", "31/02/2024 10:00:00", "2024-11-13 10:00:00", "01/01/2030 10:00:00", "13/13/2024 10:00:00"][i % 5]}
    raise KeyError(kind)


def e3(snap, packets, per_type=10):
    rnd = random.Random(SEED)
    lab_names = {lab["name"] for lab in snap.labs}
    out, rows, mutated_packets = {}, [], []
    for kind in REASON_CODES:
        picks = rnd.sample(range(len(snap.samples)), per_type)
        ok, misses = 0, []
        for i, idx in enumerate(picks):
            s = fresh(snap)
            r = dict(s.samples[idx])
            if kind == "SAMPLE_ID_DUPLICATE":
                s.samples.append(dict(r))
                s.recount()
            else:
                r.update(_mutations(r, kind, i))
            p = build_packet(r, s)
            codes = [x["code"] for x in p["reasons"]]
            if p["status"] == "needs_review" and kind in codes:
                ok += 1
            else:
                misses.append({"sample_id": snap.samples[idx]["sample_id"], "status": p["status"], "codes": codes})
            mutated_packets.append(p)
        out[kind] = {"mutated": per_type, "caught": ok, "misses": misses}
        rows.append(row(f"E3.{kind}", f"Error injection: {kind}", f"{per_type}/{per_type} needs_review with {kind}", f"{ok}/{per_type}", ok == per_type))
    fp = [p["sample_id"] for p in packets if p["status"] != "ready"]
    lab_warn = sum(1 for r in snap.samples if validate(r, snap.key_counts, lab_names, snap.date)["warnings"])
    out["false_positives_on_originals"] = {"count": len(fp), "ids": fp, "lab_not_in_l10_warnings": lab_warn}
    rows.append(row("E3.FP", "False positives on the 283 original records", "0", f"{len(fp)} of {len(packets)}", not fp,
                    f"LAB_NOT_IN_L10 warnings (non-blocking): {lab_warn}"))
    return out, rows, mutated_packets


# ---------------- E4
def _swap_digit(s):
    i = max(j for j, c in enumerate(s) if c.isdigit())
    return s[:i] + str((int(s[i]) + 1) % 10) + s[i + 1:]


def e4(snap, packets):
    ready = [p for p in packets if p["status"] == "ready"]
    passed = sum(p["fact_guard"]["passed"] for p in ready)
    uni = universe(snap)
    rnd = random.Random(SEED)
    chem = [p for p in ready if p["verdict"]["ratio"] is not None]
    villages = sorted({r["village"] for r in snap.samples})
    kinds = ["wrong_value", "wrong_permissible", "wrong_ratio", "wrong_sample_id", "wrong_target_lab", "wrong_original_lab", "wrong_village", "wrong_date", "extra_number"]
    results = Counter()
    misses = []
    total = 0
    for kind in kinds:
        for p in rnd.sample(chem, 5):
            f = facts_for(p["record"], p["verdict"], parse_value(p["record"]["value"]), p["labs"][0])
            t = p["letter"]["text"]
            if kind == "wrong_value":
                bad = t.replace(f"Reported value: {f['value_text']}", f"Reported value: {float(f['value_text']) * 1.1:.3f}")
            elif kind == "wrong_permissible":
                bad = t.replace(f"Permissible limit: {f['permissible_text']}", f"Permissible limit: {float(f['permissible_text']) + 1:g}")
            elif kind == "wrong_ratio":
                bad = t.replace(f"limit: {f['ratio_text']} times", f"limit: {float(f['ratio_text']) + 0.01:.2f} times")
            elif kind == "wrong_sample_id":
                bad = t.replace(f["sample_id"], _swap_digit(f["sample_id"]))
            elif kind == "wrong_target_lab":
                other = rnd.choice([lab["name"] for lab in snap.labs if norm_name(lab["name"]) not in (norm_name(f["target_lab"]), norm_name(f["orig_lab"]))])
                bad = t.replace(f"In-charge, {f['target_lab']}", f"In-charge, {other}")
            elif kind == "wrong_original_lab":
                other = rnd.choice([lab["name"] for lab in snap.labs if norm_name(lab["name"]) not in (norm_name(f["target_lab"]), norm_name(f["orig_lab"]))])
                bad = t.replace(f"laboratory: {f['orig_lab']}", f"laboratory: {other}")
            elif kind == "wrong_village":
                other = rnd.choice([v for v in villages if v.lower() not in {f[k].lower() for k in ("village", "gp", "block", "district")} and len(v) >= 5])
                bad = t.replace(f"Village {f['village']}", f"Village {other}")
            elif kind == "wrong_date":
                bad = t.replace(f["tested"], _swap_digit(f["tested"][:10]) + f["tested"][10:])
            else:
                bad = t + "\nThe sample was collected 3 days before testing."
            assert bad != t, (kind, p["record_id"])
            total += 1
            g = fact_guard.check(bad, f, uni)
            if g["passed"]:
                misses.append({"kind": kind, "record_id": p["record_id"]})
            else:
                results[kind] += 1
    rejected = sum(results.values())
    d = {"ready": len(ready), "template_letters_passed": passed, "injected": total, "rejected": rejected, "by_kind": dict(results), "misses": misses}
    return d, [
        row("E4a", "Template letters pass fact_guard", f"{len(ready)}/{len(ready)}", f"{passed}/{len(ready)}", passed == len(ready)),
        row("E4b", "Injected wrong numbers / ids / lab names / villages / dates rejected", f"{total}/{total}", f"{rejected}/{total}", rejected == total,
            f"{len(kinds)} kinds x 5 letters"),
    ]


# ---------------- E5
def e5():
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / "test_boundaries.py")]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", last)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", last)) else 0
    d = {"command": "pytest -q tests/test_boundaries.py", "passed": passed, "failed": failed, "summary": last}
    return d, [row("E5", "Boundary / unit tests", "all pass", f"{passed} passed, {failed} failed", r.returncode == 0 and passed > 0)]


# ---------------- E6
def e6(snap, packets, mutated):
    srcs = pinned.sources()
    s = fresh(snap)
    ars = build_packet(dict(snap.samples[0], param="Total arsenic", acceptable="0.01", permissible="0.01", value="0.050 (mg/l)"), s)
    allp = packets + [ars] + mutated
    lines = [a for p in allp for a in p["officer_actions"] + p["household_advice"]]
    unsourced = sum(1 for a in lines if not a["sources"] or any(x["id"] not in srcs for x in a["sources"]))
    table_text = {line["id"]: line["text"] for line in pinned.table()["lines"]}
    not_verbatim = sum(1 for a in lines if table_text.get(a["id"]) != a["text"])
    nr = [p for p in allp if p["status"] == "needs_review"]
    nr_with_advice = sum(1 for p in nr if p["officer_actions"] or p["household_advice"] or p["letter"])
    boil_bad = 0
    for p in allp:
        if p["status"] != "ready":
            continue
        for a in p["officer_actions"] + p["household_advice"]:
            if "boil" in a["text"].lower() and p["verdict"]["param"] != "ecoli" and not (p["verdict"]["param"] == "nitrate" and a["id"] == "H_N2"):
                boil_bad += 1
    d = {"packets_checked": len(allp), "advice_lines": len(lines), "unsourced": unsourced, "not_verbatim": not_verbatim,
         "needs_review_packets": len(nr), "needs_review_with_advice_or_letter": nr_with_advice, "forbidden_boil_lines": boil_bad}
    return d, [
        row("E6a", "Advice lines with a source id present in sources.json", f"{len(lines)}/{len(lines)}", f"{len(lines) - unsourced}/{len(lines)} (verbatim from table: {len(lines) - not_verbatim})",
            unsourced == 0 and not_verbatim == 0),
        row("E6b", "needs_review packets with any advice or letter", "0", f"{nr_with_advice} of {len(nr)}", nr_with_advice == 0),
        row("E6c", "'boil' text in chemical packets (except nitrate H_N2)", "0", str(boil_bad), boil_bad == 0, "includes synthetic arsenic packet"),
    ]


# ---------------- E7
def e7(snap, packets):
    by_id = {p["record_id"]: p for p in packets}
    order = sorted(by_id, key=lambda rid: (hashlib.sha256(by_id[rid]["sample_id"].encode()).hexdigest(), rid))[:30]
    path = ROOT / "eval" / "public_sample_30.csv"
    cols = list(snap.samples[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols + ["status", "reasons", "exceeds", "ratio", "limit_ref", "top_lab", "top_lab_same_district", "advice_ids", "fact_guard"])
        for rid in order:
            p = by_id[rid]
            v = p["verdict"] or {}
            w.writerow([p["record"][c] for c in cols] + [
                p["status"], ";".join(x["code"] for x in p["reasons"]), v.get("exceeds"), v.get("ratio"), v.get("limit_ref"),
                p["labs"][0]["name"] if p["labs"] else "", p["labs"][0]["same_district"] if p["labs"] else "",
                ";".join(a["id"] for a in p["officer_actions"] + p["household_advice"]),
                (p["fact_guard"] or {}).get("passed"),
            ])
    d = {"rule": "sort records by sha256(sample_id) ascending (ties by record id), first 30", "file": "eval/public_sample_30.csv",
         "statuses": dict(Counter(by_id[r]["status"] for r in order)), "record_ids": order}
    return d, [row("E7", "Public sample of 30 records for manual checking", "30 rows written", f"{len(order)} rows; statuses {dict(d['statuses'])}", len(order) == 30,
                   "sha256(sample_id) rule; eval/public_sample_30.csv")]


def main():
    snap = snapshot.load()  # raises if any hash differs from the manifest
    packets = [build_packet(r, snap, use_llm=False) for r in snap.samples]
    details, summary = {}, []
    for name, fn in [("E1", lambda: e1(snap, packets)), ("E2", lambda: e2(snap, packets))]:
        d, rows = fn()
        details[name], summary = d, summary + rows
    d3, rows3, mutated = e3(snap, packets)
    details["E3"], summary = d3, summary + rows3
    for name, fn in [("E4", lambda: e4(snap, packets)), ("E5", e5), ("E6", lambda: e6(snap, packets, mutated)), ("E7", lambda: e7(snap, packets))]:
        d, rows = fn()
        details[name], summary = d, summary + rows
    now = dt.datetime.now(dt.timezone.utc)
    result = {
        "statement": "These are reproducibility and safety checks on real government records, not field impact. No field users or remediation outcomes yet.",
        "command": "python eval/run_eval.py",
        "git_commit": git_commit(),
        "timestamp_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot": snap.date,
        "snapshot_hashes": {k: v["sha256"] for k, v in snap.manifest["files"].items()},
        "all_targets_met": all(r["passed"] for r in summary),
        "summary": summary,
        "details": details,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n"
    (RESULTS / f"{now.date().isoformat()}.json").write_text(text, encoding="utf-8")
    (RESULTS / "latest.json").write_text(text, encoding="utf-8")
    for r in summary:
        print(f"{r['id']:<28} {'OK ' if r['passed'] else 'FAIL'} target={r['target']} | measured={r['measured']}")
    print("all targets met:", result["all_targets_met"])


if __name__ == "__main__":
    main()
