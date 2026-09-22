#!/usr/bin/env python3
"""Install and clean MetroGIS V6.7-2.2.2.

Run this script from the MetroGIS repository root. Historical artifacts are
moved into dev/v6.7; production/test source files are not deleted.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import shutil

ROOT = Path.cwd()
if not (ROOT / "metrogis").is_dir():
    raise SystemExit(f"请在 MetroGIS 仓库根目录执行此脚本: {ROOT}")

SCRIPT_NAME = Path(__file__).name
SOURCE_NAME = "route_builder_V6_7_2_2_2.py"
UNIT_TEST_NAME = "test_route_master_quality_v6_7_2_2_2.py"
MANUAL_TEST_NAME = "test_guangzhou_line3_v6_7_2_2_2.py"

DEV = ROOT / "dev" / "v6.7"
VERSIONS = DEV / "versions"
TOOLS = DEV / "tools"
MANUAL = DEV / "manual_tests"
NOTES = DEV / "notes"
BACKUPS = DEV / "backups"
for d in (VERSIONS, TOOLS, MANUAL, NOTES, BACKUPS, ROOT / "tests"):
    d.mkdir(parents=True, exist_ok=True)

SOURCE = ROOT / SOURCE_NAME
ARCHIVED_SOURCE = VERSIONS / SOURCE_NAME
UNIT_TEST_SOURCE = ROOT / UNIT_TEST_NAME
UNIT_TEST_TARGET = ROOT / "tests" / UNIT_TEST_NAME
MANUAL_TEST_SOURCE = ROOT / MANUAL_TEST_NAME

# A previous clean-up run may already have archived the release snapshot.
# Accept it as the installation source so the fix can be re-run safely.
if not SOURCE.exists() and ARCHIVED_SOURCE.exists():
    SOURCE = ARCHIVED_SOURCE

if not SOURCE.exists():
    raise SystemExit(f"找不到发布源文件: {ROOT / SOURCE_NAME} 或 {ARCHIVED_SOURCE}")
if not UNIT_TEST_SOURCE.exists():
    raise SystemExit(f"找不到回归测试发布文件: {UNIT_TEST_SOURCE}")
if not MANUAL_TEST_SOURCE.exists():
    raise SystemExit(f"找不到广州实战测试发布文件: {MANUAL_TEST_SOURCE}")

PARSER_TARGET = ROOT / "metrogis" / "parser" / "route_builder.py"
ROOT_TARGET = ROOT / "route_builder_V6_7.py"
if not PARSER_TARGET.exists():
    raise SystemExit(f"找不到 parser route_builder.py: {PARSER_TARGET}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# Back up active files before replacement.
root_backup = BACKUPS / "route_builder_V6_7_pre_2_2_2.py.bak"
parser_backup = BACKUPS / "route_builder_parser_pre_2_2_2.py.bak"
if ROOT_TARGET.exists() and not root_backup.exists():
    shutil.copy2(ROOT_TARGET, root_backup)
if PARSER_TARGET.exists() and not parser_backup.exists():
    shutil.copy2(PARSER_TARGET, parser_backup)

# Install active source + canonical regression test.
shutil.copy2(SOURCE, ROOT_TARGET)
shutil.copy2(SOURCE, PARSER_TARGET)
shutil.copy2(UNIT_TEST_SOURCE, UNIT_TEST_TARGET)


def archive_path(src: Path, dest_dir: Path, *, preferred_name: str | None = None) -> Path:
    """Move a temporary release file into an archive directory.

    If the exact same file is already archived, remove only the redundant
    temporary copy. Otherwise use a duplicate-safe name instead of overwriting.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = preferred_name or src.name
    dest = dest_dir / name
    if dest.exists():
        if sha256(src) == sha256(dest):
            src.unlink()
            return dest
        stem = dest.stem
        suffix = dest.suffix
        index = 2
        while True:
            candidate = dest_dir / f"{stem}_copy{index}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            index += 1
    shutil.move(str(src), str(dest))
    return dest


# Archive the package files after installation so the repository root stays clean.
if SOURCE == ROOT / SOURCE_NAME and SOURCE.exists():
    archive_path(SOURCE, VERSIONS)
archive_path(UNIT_TEST_SOURCE, VERSIONS, preferred_name=f"regression_{UNIT_TEST_NAME}")
archive_path(MANUAL_TEST_SOURCE, MANUAL, preferred_name=f"manual_{MANUAL_TEST_NAME}")


def move_if_present(name: str, dest_dir: Path) -> None:
    src = ROOT / name
    if not src.exists():
        return
    archive_path(src, dest_dir)


# Archive older V6.7 snapshots, apply scripts, manual tests and notes.
for path in list(ROOT.iterdir()):
    if not path.is_file():
        continue
    name = path.name
    if name.startswith("route_builder_V6_7_") and name.endswith(".py"):
        if name != SOURCE_NAME:
            move_if_present(name, VERSIONS)
    elif name.startswith("apply_v6_7") and name.endswith(".py"):
        move_if_present(name, TOOLS)
    elif name.startswith("test_") and "v6_7" in name and name.endswith(".py"):
        move_if_present(name, MANUAL)
    elif name.startswith("README_V6_7") and name.endswith(".md"):
        move_if_present(name, NOTES)


def normalize_manual_test_names() -> None:
    """Keep manual tests explicitly runnable without pytest auto-collecting them."""
    for path in sorted(MANUAL.rglob("test_*.py")):
        target = path.with_name(f"manual_{path.name}")
        if target.exists():
            if sha256(path) == sha256(target):
                path.unlink()
            continue
        path.rename(target)


normalize_manual_test_names()

# Make every manual test import the repository package correctly regardless of
# the directory from which pytest is invoked. This conftest is non-test code and
# is intentionally kept inside the manual-test archive.
manual_conftest = MANUAL / "conftest.py"
if not manual_conftest.exists():
    manual_conftest.write_text(
        "from pathlib import Path\n"
        "import sys\n\n"
        "REPO_ROOT = Path(__file__).resolve().parents[3]\n"
        "if str(REPO_ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(REPO_ROOT))\n",
        encoding="utf-8",
    )

# Archive this installer itself so the root is left with only active source/test
# files and normal project files.
script_path = ROOT / SCRIPT_NAME
if script_path.exists():
    archive_path(script_path, TOOLS)

# Cache cleanup only.
for cache_name in ("__pycache__", ".pytest_cache"):
    for cache in ROOT.rglob(cache_name):
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)

print("MetroGIS V6.7-2.2.2 integrated and cleaned.")
print(f"active root source : {ROOT_TARGET}")
print(f"active parser      : {PARSER_TARGET}")
print(f"regression test    : {UNIT_TEST_TARGET}")
print(f"historical files   : {VERSIONS}")
print(f"tools              : {TOOLS}")
print(f"manual tests       : {MANUAL}")
print(f"notes              : {NOTES}")
print(f"backups            : {BACKUPS}")
print("Manual tests are renamed to manual_test_*.py and are not auto-collected by pytest.")
print("Release installer has been archived under dev/v6.7/tools/.")
