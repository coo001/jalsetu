"""WQMIS collector (refactor of legacy/wq.py + legacy/probe.py).

Usage: python -m collector.wqmis [--date YYYY-MM-DD]
Writes data/snapshots/<date>/ + manifest.json. Never overwrites an existing snapshot.
Every failed request is appended to collector/runs.jsonl.
"""
import argparse
import base64
import csv
import datetime as dt
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jalsetu.snapshot import SNAPSHOT_ROOT, write_manifest  # noqa: E402

BASE = "https://ejalshakti.gov.in/WQMIS"
SOURCE_URLS = {"WQ6": f"{BASE}/Report/Contaminantwise", "L10": f"{BASE}/Main/lab_parameterlist"}
KEY = b"8080808080808080"  # the site's own client-side AES key/IV (public JS)
RUNS_LOG = Path(__file__).resolve().parent / "runs.jsonl"
STATE_KEYS = ["State", "StateId", "PH", "TDS", "Turbidity", "Chloride", "Total_Alkalinity", "Total_Hardness", "Sulphate", "Iron",
              "Total_Arsenic", "Fluoride", "Nitrate", "Residual_Chlorine", "Others", "TotalColiform", "TotalEcoil"]
SAMPLE_PARAMS = ["Fluoride", "Nitrate", "Total arsenic", "Ecoil"]


def enc(v) -> str:
    """AES-128-CBC + PKCS7 + base64, as the WQMIS front-end does for query parameters."""
    p = padding.PKCS7(128).padder()
    data = p.update(str(v).encode()) + p.finalize()
    e = Cipher(algorithms.AES(KEY), modes.CBC(KEY)).encryptor()
    return base64.b64encode(e.update(data) + e.finalize()).decode()


def log_run(event: dict, path: Path = RUNS_LOG) -> None:
    event = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


class Client:
    def __init__(self, opener=None, timeout: float = 90, retries: int = 4, backoff: float = 5, sleep=time.sleep):
        if opener is None:
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            opener.addheaders = [("User-Agent", "Mozilla/5.0"), ("X-Requested-With", "XMLHttpRequest")]
        self.op, self.timeout, self.retries, self.backoff, self.sleep = opener, timeout, retries, backoff, sleep

    def _open(self, url: str, data: bytes | None = None) -> bytes:
        for i in range(self.retries):
            try:
                return self.op.open(url, data=data, timeout=self.timeout).read()
            except Exception as e:
                log_run({"event": "request_failed", "url": url.split("?")[0], "attempt": i + 1, "error": f"{type(e).__name__}: {e}"})
                if i == self.retries - 1:
                    raise
                self.sleep(self.backoff * (2 ** i))

    def start_session(self):
        self._open(SOURCE_URLS["WQ6"])

    def get(self, path: str, **kw):
        q = urllib.parse.urlencode({k: enc(v) for k, v in kw.items()})
        return json.loads(self._open(f"{BASE}/Report/{path}?{q}"))

    def post(self, path: str, **kw):
        data = urllib.parse.urlencode({k: enc(v) for k, v in kw.items()}).encode()
        return json.loads(self._open(f"{BASE}/Report/{path}/", data=data))

    def lab_page(self, state_id: int, page: int) -> list[list[str]]:
        q = urllib.parse.urlencode({"Parameter_id": enc(0), "TypeId": enc(0), "dt_Id": enc(0), "gpId": enc(0), "st_id": enc(state_id), "page": page})
        h = self._open(f"{BASE}/Main/lab_parameterlist?{q}").decode("utf-8", "ignore")
        rows = [[" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S)]
        return [r[:9] for r in rows if len(r) >= 9]


def _write_csv(path: Path, header: list[str], rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def collect(client: Client, date: str, root: Path = SNAPSHOT_ROOT, state_id: int = 2, state_code: str = "AP", fy: str = "2024-2025") -> Path:
    out = root / date
    if out.exists():
        raise FileExistsError(f"snapshot {out} already exists; refusing to overwrite")
    tmp = root / f".{date}.partial"
    tmp.mkdir(parents=True, exist_ok=False)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client.start_session()
    for year in ["2024-2025", "2025-2026"]:
        d = client.get("GetContaminantwiseData", cpage=1, st=0, dt=0, bl=0, gp=0, vill=0, fy=year, IsPws=1, SchemeId=0, SampleType=0)
        _write_csv(tmp / f"wq6_states_{year}.csv", STATE_KEYS, [[r.get(k) for k in STATE_KEYS] for r in d["Contaminantwise"]])
    samples = []
    for p in SAMPLE_PARAMS:
        first = client.post("ContaminantwiseVillagefil", cpage=1, paraname=p, stid=state_id, dtid=0, blid=0, gpid=0, villid=0, fy=fy)
        vills = list(first["Contaminantwise"])
        for pg in range(2, int(first.get("TotalPage") or 1) + 1):
            vills += client.post("ContaminantwiseVillagefil", cpage=pg, paraname=p, stid=state_id, dtid=0, blid=0, gpid=0, villid=0, fy=fy)["Contaminantwise"]
        for x in vills:
            for y in client.post("Contaminantwisesamplefillist", cpage=1, paraname=p, stid=state_id, dtid=x["DistrictId"], villid=x["VillageId"], fy=fy)["Contaminantwise"]:
                samples.append([p, y["District"], y["Block"], y["Grampanchayat"], y["Village"], x["VillageId"], y["SampleId"], y["sample_sourceName"],
                                y["Acceptablelimit"], y["Permissiblelimit"], y["Parametervalue"], y["labname"], y["s_report_approval_action_time"]])
    _write_csv(tmp / f"wq6_{state_code}_{fy}_samples.csv",
               ["param", "district", "block", "gp", "village", "village_id", "sample_id", "source", "acceptable", "permissible", "value", "lab", "tested"], samples)
    labs, names = [], set()
    for page in range(1, 50):
        new = [r for r in client.lab_page(state_id, page) if r[1] not in names]
        if not new:
            break
        labs += new
        names |= {r[1] for r in new}
    _write_csv(tmp / f"wq_labs_{state_code}_L10.csv", ["sno", "name", "group", "address", "established", "accredited", "lat", "lon", "parameters"], labs)
    write_manifest(tmp, retrieved, SOURCE_URLS)
    tmp.rename(out)
    log_run({"event": "snapshot_written", "dir": str(out), "samples": len(samples), "labs": len(labs)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)
    try:
        print(collect(Client(), args.date))
    except Exception as e:
        log_run({"event": "collect_failed", "date": args.date, "error": f"{type(e).__name__}: {e}"})
        raise


if __name__ == "__main__":
    main()
