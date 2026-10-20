"""Unpack and check BIRD dev (SPEC 8). Prints the BIRD_DIR and BIRD_DB_DIR to set.

The release has a zip inside the zip (dev_databases.zip); both levels are handled, and an
input that Kaggle already unpacked works too. --write-manifest records sha256 of dev.json and
of every database (first local run, committed); --check-manifest verifies against it.
  python scripts/get_bird.py --zip dev.zip --dest data/bird \
    --write-manifest results/bird_manifest.json
  python scripts/get_bird.py --extracted /kaggle/input/bird --dest /tmp/bird \
    --check-manifest results/bird_manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from collections.abc import Sequence
from pathlib import Path

from spider_sql.bird import BirdPaths, check_counts, load_bird
from spider_sql.bundle import sha256_file

SKIP = ("__MACOSX",)


def unzip(path: Path, dest: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        for member in zf.infolist():
            if not any(part in SKIP for part in Path(member.filename).parts):
                zf.extract(member, dest)


def find(root: Path, name: str, is_dir: bool) -> list[Path]:
    hits = []
    for d, dirs, files in os.walk(root, followlinks=True):
        if any(part in SKIP for part in Path(d).parts):
            continue
        if (name in dirs) if is_dir else (name in files):
            hits.append(Path(d) / name)
    return sorted(hits)


def locate(root: Path, dest: Path) -> BirdPaths:
    questions = [p for p in find(root, "dev.json", False) if "dev_databases" not in p.parts]
    if len(questions) != 1:
        raise SystemExit(f"expected one dev.json under {root}, found {questions}")
    dbs = [p for p in find(root, "dev_databases", True) if any(p.glob("*/*.sqlite"))]
    if not dbs:
        inner = find(root, "dev_databases.zip", False)
        if not inner:
            raise SystemExit("no dev_databases folder or dev_databases.zip found")
        print(f"unpacking {inner[0]}")
        unzip(inner[0], dest / "inner")
        dbs = [p for p in find(dest / "inner", "dev_databases", True) if any(p.glob("*/*.sqlite"))]
    if len(dbs) != 1:
        raise SystemExit(f"expected one dev_databases folder, found {dbs}")
    return BirdPaths(questions=questions[0], databases=dbs[0])


def manifest(paths: BirdPaths, db_ids: list[str]) -> dict[str, str]:
    files = {"dev.json": sha256_file(paths.questions)}
    for d in db_ids:
        files[f"dev_databases/{d}/{d}.sqlite"] = sha256_file(paths.sqlite(d))
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", type=Path)
    src.add_argument("--extracted", type=Path)
    parser.add_argument("--dest", type=Path, required=True)
    out = parser.add_mutually_exclusive_group(required=True)
    out.add_argument("--write-manifest", type=Path)
    out.add_argument("--check-manifest", type=Path)
    args = parser.parse_args(argv)

    args.dest.mkdir(parents=True, exist_ok=True)
    if args.zip:
        print(f"zip sha256 {sha256_file(args.zip)}")
        unzip(args.zip, args.dest)
        root = args.dest
    else:
        root = args.extracted
    paths = locate(root, args.dest)
    examples = load_bird(paths.questions)
    counts = check_counts(examples, paths)
    db_ids = sorted(counts["databases"])  # type: ignore[call-overload]
    files = manifest(paths, db_ids)
    if args.write_manifest:
        record = {"release": "BIRD dev, https://bird-bench.github.io/", **counts, "sha256": files}
        args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"manifest written: {args.write_manifest}")
    else:
        expected = json.loads(args.check_manifest.read_text(encoding="utf-8"))["sha256"]
        bad = sorted(k for k in expected.keys() | files.keys() if expected.get(k) != files.get(k))
        if bad:
            raise SystemExit(f"files differ from the manifest: {bad}")
        print("all files match the manifest")
    spider = os.environ.get("SPIDER_DIR")
    if spider:
        from spider_sql.data import load_examples, load_train

        spider_dbs = {e.db_id for e in load_train(Path(spider))}
        spider_dbs |= {e.db_id for s in ("dev", "test") for e in load_examples(Path(spider), s)}
        print(f"database names shared with Spider: {sorted(spider_dbs & set(db_ids)) or 'none'}")
    print(f"{counts['n']} questions, {len(db_ids)} databases")
    print(f"BIRD_DIR={paths.questions.parent}")
    print(f"BIRD_DB_DIR={paths.databases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
