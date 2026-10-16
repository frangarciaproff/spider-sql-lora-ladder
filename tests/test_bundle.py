import zipfile
from pathlib import Path

import pytest

from spider_sql.bundle import (
    MARKER,
    build_bundle,
    install_bundle,
    plan_bundle,
    read_sidecar,
    sha256_file,
)


def names(spider_tree: tuple[Path, Path]) -> set[str]:
    return {arc for _, arc in plan_bundle(*spider_tree)}


def test_plan_selects_expected_files(spider_tree: tuple[Path, Path]) -> None:
    got = names(spider_tree)
    assert "spider/dev.json" in got
    assert "spider/database/a/a.sqlite" in got
    assert "spider/test_database/e/e.sqlite" in got
    assert "testsuite/database/d/dv1.sqlite" in got
    assert "testsuite/database/d/d.sqlite" in got


def test_plan_excludes_junk_and_unneeded(spider_tree: tuple[Path, Path]) -> None:
    got = names(spider_tree)
    assert not any(".DS_Store" in n or "__MACOSX" in n for n in got)
    assert not any("zz_not_in_test" in n for n in got)
    assert not any("d2_not_dev" in n for n in got)


def test_plan_fails_on_missing_top_level_file(spider_tree: tuple[Path, Path]) -> None:
    (spider_tree[0] / "tables.json").unlink()
    with pytest.raises(FileNotFoundError):
        plan_bundle(*spider_tree)


def test_roundtrip_build_and_install(spider_tree: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "dist" / "bundle.zip"
    digest = build_bundle(plan_bundle(*spider_tree), out)
    assert digest == sha256_file(out)
    assert read_sidecar(out) == digest
    with zipfile.ZipFile(out) as archive:
        assert "MANIFEST.json" in archive.namelist()
    dest = tmp_path / "colab"
    spider, suite = install_bundle(out, dest, digest)
    assert (spider / "dev.json").is_file()
    assert (suite / "database" / "d" / "dv1.sqlite").is_file()
    assert (dest / MARKER).read_text() == digest
    assert not (dest / "bundle.zip").exists()


def test_install_is_idempotent(spider_tree: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "bundle.zip"
    digest = build_bundle(plan_bundle(*spider_tree), out)
    dest = tmp_path / "colab"
    install_bundle(out, dest, digest)
    out.unlink()  # a second call must not need the zip
    spider, _ = install_bundle(out, dest, digest)
    assert (spider / "dev.json").is_file()


def test_install_rejects_wrong_checksum(spider_tree: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "bundle.zip"
    build_bundle(plan_bundle(*spider_tree), out)
    dest = tmp_path / "colab"
    with pytest.raises(ValueError):
        install_bundle(out, dest, "0" * 64)
    assert not (dest / "spider").exists()
