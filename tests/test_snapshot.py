import json
import shutil

import pytest

from jalsetu import snapshot


def test_manifest_hashes_verify():
    m = snapshot.verify(snapshot.SNAPSHOT_ROOT / "2026-11-09")
    assert m["retrieved_utc"] == "2026-11-09T01:53:38Z"
    assert m["files"]["wq6_AP_2024-2025_samples.csv"]["rows"] == 283
    assert m["files"]["wq_labs_AP_L10.csv"]["rows"] == 138
    assert m["files"]["wq_labs_BR_L10.csv"]["rows"] == 123
    assert m["files"]["wq6_BR_2024-2025_arsenic_samples.csv"]["rows"] == 592
    assert m["files"]["wq6_BR_2024-2025_arsenic_samples.csv"]["retrieved_utc"] == "2026-11-09T06:35:29Z"
    assert m["files"]["br_arsenic_log.json"]["retrieved_utc"] == "2026-11-09T06:35:29Z"
    assert m["files"]["wq6_AP_2024-2025_samples.csv"]["retrieved_utc"] == "2026-11-09T01:53:38Z"
    assert set(m["source_urls"]) == {"WQ6", "L10"}
    for meta in m["files"].values():
        assert len(meta["sha256"]) == 64


def test_tampered_file_detected(tmp_path):
    d = tmp_path / "2026-11-09"
    shutil.copytree(snapshot.SNAPSHOT_ROOT / "2026-11-09", d)
    with (d / "wq_labs_AP_L10.csv").open("a") as f:
        f.write("x\n")
    with pytest.raises(snapshot.SnapshotError, match="wq_labs_AP_L10.csv"):
        snapshot.verify(d)


def test_missing_manifest(tmp_path):
    with pytest.raises(snapshot.SnapshotError):
        snapshot.verify(tmp_path)


def test_manifest_covers_every_snapshot_file():
    d = snapshot.SNAPSHOT_ROOT / "2026-11-09"
    m = snapshot.verify(d)
    on_disk = {p.name for p in d.iterdir() if p.is_file() and p.name != "manifest.json"}
    assert on_disk == set(m["files"])
    assert {"wq6_BR_2024-2025_arsenic_samples.csv", "br_arsenic_log.json"} <= set(m["files"])


def test_tampered_br_file_detected(tmp_path):
    d = tmp_path / "2026-11-09"
    shutil.copytree(snapshot.SNAPSHOT_ROOT / "2026-11-09", d)
    with (d / "wq6_BR_2024-2025_arsenic_samples.csv").open("a") as f:
        f.write("x\n")
    with pytest.raises(snapshot.SnapshotError, match="wq6_BR_2024-2025_arsenic_samples.csv"):
        snapshot.verify(d)


def test_records_tagged_with_state(_snap):
    from collections import Counter
    assert Counter(r["state"] for r in _snap.samples) == Counter({"AP": 283, "BR": 592})
    assert len(_snap.labs_for("AP")) == 138 and len(_snap.labs_for("BR")) == 123
    ids = [snapshot.record_id(r) for r in _snap.samples]
    assert len(ids) == len(set(ids))
