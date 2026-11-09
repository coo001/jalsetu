"""JalSetu web app: static HTML + vanilla JS over a small JSON API."""
import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import usage
from jalsetu import pinned, snapshot
from jalsetu.pipeline import build_packet
from jalsetu.units import parse_value

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
EVAL_LATEST = ROOT / "eval" / "results" / "latest.json"


@asynccontextmanager
async def lifespan(_app):
    yield
    if usage.enabled():
        usage.log_snapshot()


app = FastAPI(title="JalSetu", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@lru_cache(maxsize=1)
def state():
    snap = snapshot.load()
    packets = {}
    for r in snap.samples:
        p = build_packet(r, snap, use_llm=False)
        packets[p["record_id"]] = p
    return snap, packets


def count(request: Request, template: str) -> bool:
    """Count one hit on a fixed route template; nothing from the request is stored."""
    if usage.should_count(request.url.path, request.headers.get("user-agent")):
        usage.record(template)
        return True
    return False


@app.get("/healthz")
def healthz():
    return {"ok": True}


STATE_NAMES = {"AP": "Andhra Pradesh", "BR": "Bihar"}


def retrieved_by_state(snap) -> dict:
    files = snap.manifest["files"]
    return {st: files[names[0]].get("retrieved_utc", snap.manifest["retrieved_utc"]) for st, (names, _) in snapshot.STATE_FILES.items()}


def footer(snap) -> str:
    when = ", ".join(f"{st} {t}" for st, t in retrieved_by_state(snap).items())
    return (
        f'<footer>Data snapshot: {snap.date} (WQMIS, retrieved {when}). '
        "Decision support only. A qualified officer must confirm every action. "
        'Code: MIT License. <a href="/sources">Sources</a> · <a href="/eval">Evaluation</a></footer>'
    )


def page(name: str) -> HTMLResponse:
    snap, _ = state()
    body = (STATIC / f"{name}.html").read_text(encoding="utf-8")
    return HTMLResponse(body.replace("{{FOOTER}}", footer(snap)).replace("{{SNAPSHOT}}", snap.date))


@app.get("/", response_class=HTMLResponse)
def overview_page(request: Request):
    count(request, "/")
    return page("index")


@app.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request):
    count(request, "/queue")
    return page("queue")


@app.get("/sample/{rid}", response_class=HTMLResponse)
def sample_page(rid: str, request: Request):
    count(request, "/sample/{id}")
    return page("sample")


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    count(request, "/sources")
    return page("sources")


@app.get("/eval", response_class=HTMLResponse)
def eval_page(request: Request):
    count(request, "/eval")
    return page("eval")


@app.get("/api/meta")
def api_meta():
    snap, _ = state()
    return {"snapshot": snap.date, "retrieved_utc": snap.manifest["retrieved_utc"], "retrieved_utc_by_state": retrieved_by_state(snap),
            "source_urls": snap.manifest["source_urls"]}


@app.get("/api/overview")
def api_overview():
    snap, packets = state()
    by_state = {}
    for st in snapshot.STATE_FILES:
        ps = [p for p in packets.values() if p["state"] == st]
        by_state[st] = {
            "name": STATE_NAMES[st],
            "retrieved_utc": retrieved_by_state(snap)[st],
            "records": len(ps),
            "by_param": Counter(p["record"]["param"] for p in ps),
            "by_status": Counter(p["status"] for p in ps),
            "districts": len({p["record"]["district"] for p in ps}),
            "villages": len({p["record"]["village_id"] for p in ps}),
            "l10_labs": len(snap.labs_for(st)),
        }
    return {
        "caption": f"Villages with at least one contaminated sample, by parameter (a village can appear under several parameters; not a count of people). Source: WQMIS WQ6, retrieved {snap.manifest['retrieved_utc']}.",
        "states": snap.states,
        "by_state": by_state,
    }


def _row(p: dict) -> dict:
    r, v = p["record"], p["verdict"] or {}
    pv = parse_value(r.get("value"))
    return {
        "record_id": p["record_id"],
        "state": p["state"],
        "sample_id": p["sample_id"],
        "village": r.get("village"),
        "district": r.get("district"),
        "param": v.get("param_display") or r.get("param"),
        "value": pv["number"],
        "unit": v.get("unit") or pv["unit_raw"],
        "permissible": v.get("permissible"),
        "ratio": v.get("ratio"),
        "tested": r.get("tested"),
        "status": p["status"],
        "value_extreme": any(w["code"] == "VALUE_EXTREME" for w in p["warnings"]),
    }


@app.get("/api/samples")
def api_samples():
    _, packets = state()
    rows = [_row(p) for p in packets.values()]
    rows.sort(key=lambda x: (x["ratio"] is None, -(x["ratio"] or 0), x["record_id"]))
    return rows


@app.get("/api/packet/{rid}")
def api_packet(rid: str, request: Request):
    snap, packets = state()
    counted = count(request, "/api/packet/{id}")
    if rid not in packets:
        matches = [k for k, p in packets.items() if p["sample_id"] == rid]
        if not matches:
            raise HTTPException(404, f"no record {rid!r} in snapshot {snap.date}")
        if len(matches) > 1:
            return JSONResponse(status_code=409, content={"detail": "sample id is listed under several parameters; choose one", "record_ids": matches})
        rid = matches[0]
    p = packets[rid]
    if os.environ.get("GEMINI_API_KEY") and p["status"] == "ready":
        p = build_packet(p["record"], snap, use_llm=True)
    if counted:
        usage.record(f"status:{p['status']}")
    return p


@app.post("/api/usage/print", status_code=204)
def api_usage_print(request: Request):
    count(request, "print")


@app.get("/api/stats")
def api_stats():
    return usage.stats()


@app.get("/api/sources")
def api_sources():
    return {"sources": list(pinned.sources().values()), "limits": pinned.limits(), "lines": pinned.table()["lines"], "mapping": pinned.mapping()}


@app.get("/api/eval/latest")
def api_eval_latest():
    if not EVAL_LATEST.exists():
        raise HTTPException(404, "no evaluation results yet; run `make eval`")
    return json.loads(EVAL_LATEST.read_text(encoding="utf-8"))
