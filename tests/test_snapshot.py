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
