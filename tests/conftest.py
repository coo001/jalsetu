import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jalsetu import snapshot as snap_mod  # noqa: E402


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture(scope="session")
def _snap():
    return snap_mod.load()


@pytest.fixture
def snap(_snap):
    s = copy.copy(_snap)
    s.samples = [dict(r) for r in _snap.samples]
    s.labs = [dict(l) for l in _snap.labs]
    s.recount()
    return s


@pytest.fixture
def rec(snap):
    return dict(snap.samples[0])
