"""Build and install the data bundle that travels through Google Drive to Colab."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from spider_sql.data import load_examples

TOP_LEVEL_FILES = (
    "README.txt",
    "train_spider.json",
    "train_others.json",
    "dev.json",
    "test.json",
    "tables.json",
    "test_tables.json",
    "train_gold.sql",
    "dev_gold.sql",
    "test_gold.sql",
)
EXCLUDED_NAMES = frozenset({".DS_Store"})
EXCLUDED_DIRS = frozenset({"__MACOSX"})
MARKER = ".bundle_sha256"


def _walk(root: Path) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"missing folder: {root}")
    return [
        p
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name not in EXCLUDED_NAMES and not EXCLUDED_DIRS & set(p.parts)
    ]


def plan_bundle(spider_dir: Path, testsuite_dir: Path) -> list[tuple[Path, str]]:
    """List (source, archive name). Test-suite files only for dev DBs, test DBs only for test."""
    dev_dbs = {e.db_id for e in load_examples(spider_dir, "dev")}
    test_dbs = {e.db_id for e in load_examples(spider_dir, "test")}
    plan: list[tuple[Path, str]] = []
    for name in TOP_LEVEL_FILES:
        source = spider_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"missing file: {source}")
        plan.append((source, f"spider/{name}"))
    for path in _walk(spider_dir / "database"):
        plan.append((path, f"spider/{path.relative_to(spider_dir).as_posix()}"))
    for db_id in sorted(test_dbs):
        for path in _walk(spider_dir / "test_database" / db_id):
            plan.append((path, f"spider/{path.relative_to(spider_dir).as_posix()}"))
    for db_id in sorted(dev_dbs):
        for path in _walk(testsuite_dir / "database" / db_id):
            plan.append((path, f"testsuite/{path.relative_to(testsuite_dir).as_posix()}"))
    names = [arc for _, arc in plan]
    if len(names) != len(set(names)):
        raise ValueError("duplicate archive names in bundle plan")
    return plan


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def build_bundle(plan: list[tuple[Path, str]], out_zip: Path) -> str:
    """Write the zip plus a .sha256 sidecar. Returns the sha256."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"files": [{"path": arc, "bytes": src.stat().st_size} for src, arc in plan]}
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, arc in plan:
            archive.write(source, arc)
        archive.writestr("MANIFEST.json", json.dumps(manifest, indent=1))
    digest = sha256_file(out_zip)
    sidecar_path(out_zip).write_text(f"{digest}  {out_zip.name}\n", encoding="utf-8")
    return digest


def sidecar_path(zip_path: Path) -> Path:
    return zip_path.with_name(zip_path.name + ".sha256")


def read_sidecar(zip_path: Path) -> str | None:
    path = sidecar_path(zip_path)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").split()[0]


def install_bundle(zip_path: Path, dest: Path, expected_sha256: str) -> tuple[Path, Path]:
    """Copy to local disk, verify, extract. Returns (spider_dir, testsuite_dir). Idempotent."""
    spider, testsuite = dest / "spider", dest / "testsuite"
    marker = dest / MARKER
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == expected_sha256:
        return spider, testsuite
    dest.mkdir(parents=True, exist_ok=True)
    local = dest / zip_path.name
    shutil.copyfile(zip_path, local)
    digest = sha256_file(local)
    if digest != expected_sha256:
        local.unlink()
        raise ValueError(f"checksum mismatch: expected {expected_sha256}, got {digest}")
    with zipfile.ZipFile(local) as archive:
        archive.extractall(dest)
    local.unlink()
    marker.write_text(digest, encoding="utf-8")
    return spider, testsuite
