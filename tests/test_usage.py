import json
import re

import pytest
from fastapi.testclient import TestClient

from app import usage
from app.main import app

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED = usage.ROUTES | {"print"} | {f"status:{s}" for s in ("ready", "needs_review")}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("JALSETU_DISABLE_USAGE", raising=False)
    usage.reset()
    yield TestClient(app)
    usage.reset()


def total(name):
    return sum(c.get(name, 0) for c in usage.snapshot().values())


def test_counts_routes_and_status(client):
    sid = client.get("/api/samples").json()[0]["record_id"]
    client.get("/?x=secret")
    client.get("/queue")
    client.get(f"/sample/{sid}")
    client.get("/sources")
    client.get("/eval")
    p = client.get(f"/api/packet/{sid}").json()
    assert client.post("/api/usage/print").status_code == 204
    for r in usage.ROUTES:
        assert total(r) == 1, r
    assert total(f"status:{p['status']}") == 1 and total("print") == 1


def test_bots_and_health_ignored(client):
    for ua in ("Googlebot/2.1", "Baiduspider", "CCBot crawler", "Render/1.0"):
        client.get("/", headers={"User-Agent": ua})
    assert client.get("/healthz").json() == {"ok": True}
    assert usage.snapshot() == {}


def test_no_identifiers_stored(client):
    sid = client.get("/api/samples").json()[0]["record_id"]
    client.get(f"/sample/{sid}?q=abc", headers={"User-Agent": "Mozilla/5.0 unique-ua-xyz", "Cookie": "c=1"})
    client.get(f"/api/packet/{sid}")
    snap = usage.snapshot()
    assert snap and all(DATE.match(d) for d in snap)
    assert all(k in ALLOWED for c in snap.values() for k in c)
    blob = json.dumps(snap)
    for s in (sid, "abc", "unique-ua-xyz", "testclient", "c=1"):
        assert s not in blob


def test_disable_env(client, monkeypatch):
    monkeypatch.setenv("JALSETU_DISABLE_USAGE", "1")
    client.get("/")
    client.post("/api/usage/print")
    assert usage.snapshot() == {} and client.get("/api/stats").json()["enabled"] is False


def test_stats_and_snapshot_log(client, capsys):
    for _ in range(usage.SNAPSHOT_EVERY):
        client.get("/sources")
    line = [l for l in capsys.readouterr().out.splitlines() if "usage_snapshot" in l]
    assert len(line) == 1 and json.loads(line[0])["since_utc"] == usage.SINCE_UTC
    st = client.get("/api/stats").json()
    assert st["note"] == usage.NOTE and st["since_utc"] == usage.SINCE_UTC and total("/sources") == 50


def test_eval_page_counters_heading(client):
    t = client.get("/eval").text
    assert "Deployment counters" in t and usage.NOTE in t
