"""AI-assisted re-comparison of 10 public-sample records against live WQMIS (not a human check).
Re-fetches each record's village from WQMIS and compares value, limits, lab and test date with the stored snapshot rows,
and compares the limits with the IS 10500 table values pinned in jalsetu/guidance. Run: python eval/recheck_live.py"""
import csv, json, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.wqmis import Client

PINNED = {"Fluoride": ("1", "1.5"), "Nitrate": ("45", "45"), "Total arsenic": ("0.01", "0.01")}  # IS 10500 limits as WQMIS prints them
def num(s): 
    try: return float(str(s).split()[0])
    except Exception: return None

def pick(path, n):
    rows = list(csv.DictReader(open(ROOT / "eval" / path, encoding="utf-8")))
    return rows[:n]

def main():
    cases = [("AP", 2, r) for r in pick("public_sample_30.csv", 5)] + [("BR", 5, r) for r in pick("public_sample_30_BR.csv", 5)]
    c = Client(timeout=120, retries=3); c.start_session()
    out = []
    for st, sid, r in cases:
        p = r["param"]
        live = c.post("Contaminantwisesamplefillist", cpage=1, paraname=p, stid=sid, dtid=0, villid=int(r["village_id"]), fy="2024-2025")["Contaminantwise"]
        m = [y for y in live if y["SampleId"] == r["sample_id"]]
        rec = {"state": st, "param": p, "sample_id": r["sample_id"], "found_live": bool(m)}
        if m:
            y = m[0]
            rec |= {"live_value": y["Parametervalue"], "stored_value": r["value"], "value_match": num(y["Parametervalue"]) == num(r["value"]),
                    "live_limits": [y["Acceptablelimit"], y["Permissiblelimit"]], "limits_match_stored": [num(y["Acceptablelimit"]), num(y["Permissiblelimit"])] == [num(r["acceptable"]), num(r["permissible"])],
                    "limits_match_IS10500_pinned": [num(y["Acceptablelimit"]), num(y["Permissiblelimit"])] == [num(PINNED[p][0]), num(PINNED[p][1])],
                    "lab_match": y["labname"] == r["lab"], "tested_match": y["s_report_approval_action_time"] == r["tested"],
                    "exceeds_by_hand": num(y["Parametervalue"]) > (num(y["Permissiblelimit"]) if num(y["Permissiblelimit"]) is not None else num(y["Acceptablelimit"]))}
        out.append(rec)
    keys = ["value_match", "limits_match_stored", "limits_match_IS10500_pinned", "lab_match", "tested_match"]
    mism = [o for o in out if not o["found_live"] or not all(o.get(k) for k in keys)]
    res = {"method": "AI-assisted re-comparison against live WQMIS (re-fetched per village); not a human check; same author/tooling as the collector",
           "run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "records": len(out), "mismatching_records": len(mism), "details": out}
    (ROOT / "eval" / "results" / "recheck_live_10.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(len(out), "records,", len(mism), "mismatching"); [print(json.dumps(m, ensure_ascii=False)) for m in mism]

if __name__ == "__main__": main()
