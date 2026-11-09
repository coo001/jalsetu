"""Collector tests: no network. The opener is a fake."""
import io
import json

import pytest

from collector import wqmis


class FakeOpener:
    def __init__(self, fail_times=0):
        self.fail_times, self.calls = fail_times, []

    def open(self, url, data=None, timeout=None):
        self.calls.append((url, data, timeout))
        if len(self.calls) <= self.fail_times:
            raise TimeoutError("simulated")
        return io.BytesIO(json.dumps({"ok": 1}).encode())


def test_enc_matches_legacy_scheme():
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    import base64
    raw = base64.b64decode(wqmis.enc("2024-2025"))
    d = Cipher(algorithms.AES(wqmis.KEY), modes.CBC(wqmis.KEY)).decryptor()
    u = padding.PKCS7(128).unpadder()
    assert (u.update(d.update(raw) + d.finalize()) + u.finalize()) == b"2024-2025"
    assert wqmis.enc(0) == wqmis.enc("0")


def test_retry_backoff_and_log(tmp_path, monkeypatch):
    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(wqmis, "RUNS_LOG", log)
    monkeypatch.setattr(wqmis.log_run, "__defaults__", (log,))
    sleeps = []
    op = FakeOpener(fail_times=2)
    c = wqmis.Client(opener=op, timeout=7, retries=4, backoff=1, sleep=sleeps.append)
    assert c.get("X", a=1) == {"ok": 1}
    assert sleeps == [1, 2] and all(t == 7 for _, _, t in op.calls)
    lines = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(lines) == 2 and lines[0]["event"] == "request_failed"


def test_gives_up(tmp_path, monkeypatch):
    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(wqmis.log_run, "__defaults__", (log,))
    c = wqmis.Client(opener=FakeOpener(fail_times=99), retries=3, backoff=0, sleep=lambda s: None)
    with pytest.raises(TimeoutError):
        c.post("X", a=1)
    assert len(log.read_text().splitlines()) == 3


def test_never_overwrites(tmp_path):
    (tmp_path / "2026-11-09").mkdir()
    with pytest.raises(FileExistsError):
        wqmis.collect(wqmis.Client(opener=FakeOpener()), "2026-11-09", root=tmp_path)
