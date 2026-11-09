import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/queue", "/sources", "/eval", "/sample/U704038S24873916-fluoride"])
def test_pages(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "Decision support only. A qualified officer must confirm every action." in r.text and "MIT" in r.text and "2026-11-09" in r.text


def test_eval_page_honesty_line(client):
    assert "not field impact. No field users or remediation outcomes yet." in client.get("/eval").text


def test_samples(client):
    rows = client.get("/api/samples").json()
    assert len(rows) == 283
    ratios = [r["ratio"] for r in rows if r["ratio"] is not None]
    assert ratios == sorted(ratios, reverse=True)


def test_packet(client):
    p = client.get("/api/packet/U704038S24873916").json()
    assert p["status"] == "ready" and p["fact_guard"]["passed"] and p["lab_limit_note"].startswith("Candidate labs are listed only")


def test_packet_ambiguous_and_missing(client):
    assert client.get("/api/packet/U713978S20862404").status_code == 409
    assert client.get("/api/packet/U713978S20862404-nitrate").json()["status"] == "ready"
    assert client.get("/api/packet/NOPE").status_code == 404


def test_overview_caption(client):
    d = client.get("/api/overview").json()
    assert d["caption"].startswith("Villages with at least one contaminated sample, by parameter")
    assert len(d["states"]) == 34


def test_sources(client):
    assert len(client.get("/api/sources").json()["sources"]) == 7
