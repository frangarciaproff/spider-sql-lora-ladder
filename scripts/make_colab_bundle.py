"""Pack the Spider files Colab needs into one zip (upload it to Drive)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from spider_sql.bundle import build_bundle, plan_bundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider-dir", type=Path, required=True, help="folder with dev.json")
    parser.add_argument(
        "--testsuite-dir", type=Path, required=True, help="folder that contains database/"
    )
    parser.add_argument("--out", type=Path, default=Path("dist/spider_bundle.zip"))
    args = parser.parse_args(argv)

    plan = plan_bundle(args.spider_dir, args.testsuite_dir)
    total = sum(src.stat().st_size for src, _ in plan)
    print(f"{len(plan)} files, {total / 1e9:.2f} GB uncompressed -> {args.out}")
    digest = build_bundle(plan, args.out)
    print(f"zip: {args.out.stat().st_size / 1e9:.2f} GB")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
