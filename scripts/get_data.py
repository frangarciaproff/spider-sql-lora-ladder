"""Colab side: copy the bundle from Drive to local disk, verify its checksum, extract.

Prints the two environment variables the rest of the code reads.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from spider_sql.bundle import install_bundle, read_sidecar


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True, help="bundle zip, e.g. on Drive")
    parser.add_argument("--dest", type=Path, default=Path("/content/data"))
    parser.add_argument("--sha256", default=None, help="defaults to the .sha256 sidecar")
    args = parser.parse_args(argv)

    expected = args.sha256 or read_sidecar(args.zip)
    if expected is None:
        print("no checksum: pass --sha256 or keep the .sha256 file next to the zip")
        return 2
    spider, testsuite = install_bundle(args.zip, args.dest, expected)
    print(f"SPIDER_DIR={spider}")
    print(f"TESTSUITE_DIR={testsuite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
