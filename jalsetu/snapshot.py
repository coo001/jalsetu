"""Load a dated WQMIS snapshot directory and verify it against its manifest."""
import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = ROOT / "data" / "snapshots"
DEFAULT_SNAPSHOT = "2026-11-09"

SAMPLES_FILE = "wq6_AP_2024-2025_samples.csv"
LABS_FILE = "wq_labs_AP_L10.csv"
STATES_FILE = "wq6_states_2024-2025.csv"


class SnapshotError(Exception):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_rows(path: Path) -> int | None:
    if path.suffix != ".csv":
        return None
    with path.open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def write_manifest(snap_dir: Path, retrieved_utc: str, source_urls: dict) -> dict:
    files = {}
    for p in sorted(snap_dir.iterdir()):
        if p.name == "manifest.json" or not p.is_file():
            continue
        files[p.name] = {"sha256": sha256_file(p), "rows": count_rows(p)}
    manifest = {
        "snapshot": snap_dir.name,
        "retrieved_utc": retrieved_utc,
        "source_urls": source_urls,
        "files": files,
    }
    (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(snap_dir: Path) -> dict:
    """Return the manifest if every listed file matches its sha256 and row count; raise otherwise."""
    mpath = snap_dir / "manifest.json"
    if not mpath.exists():
        raise SnapshotError(f"manifest.json missing in {snap_dir}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    problems = []
    for name, meta in manifest["files"].items():
        p = snap_dir / name
        if not p.exists():
            problems.append(f"{name}: missing")
            continue
        if sha256_file(p) != meta["sha256"]:
            problems.append(f"{name}: sha256 mismatch")
        if meta.get("rows") is not None and count_rows(p) != meta["rows"]:
            problems.append(f"{name}: row count mismatch")
    if problems:
        raise SnapshotError("; ".join(problems))
    return manifest


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass
class Snapshot:
    dir: Path
    manifest: dict
    samples: list[dict]
    labs: list[dict]
    states: list[dict]
    key_counts: Counter = field(default_factory=Counter)

    @property
    def date(self) -> str:
        return self.dir.name

    def recount(self) -> None:
        self.key_counts = Counter(record_key(r) for r in self.samples)


def record_key(r: dict) -> tuple[str, str]:
    """A sample can be listed under several parameters; duplicates are judged per (sample_id, param)."""
    return ((r.get("sample_id") or "").strip(), " ".join((r.get("param") or "").split()).lower())


def record_id(r: dict) -> str:
    from .pinned import param_key

    pk = param_key(r.get("param", "")) or "unknown"
    return f"{(r.get('sample_id') or '').strip()}-{pk}"


def load(snap_dir: Path | None = None, verify_hashes: bool = True) -> Snapshot:
    snap_dir = Path(snap_dir) if snap_dir else SNAPSHOT_ROOT / DEFAULT_SNAPSHOT
    manifest = verify(snap_dir) if verify_hashes else json.loads((snap_dir / "manifest.json").read_text())
    snap = Snapshot(
        dir=snap_dir,
        manifest=manifest,
        samples=_read_csv(snap_dir / SAMPLES_FILE),
        labs=_read_csv(snap_dir / LABS_FILE),
        states=_read_csv(snap_dir / STATES_FILE),
    )
    snap.recount()
    return snap
