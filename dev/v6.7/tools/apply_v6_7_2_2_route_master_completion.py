#!/usr/bin/env python3
"""Install MetroGIS V6.7-2.2 Route Master endpoint completion."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path.cwd()
SOURCE = ROOT / "route_builder_V6_7_2_2.py"
TARGET_ROOT = ROOT / "route_builder_V6_7.py"
TARGET_PARSER = ROOT / "metrogis" / "parser" / "route_builder.py"
TEST_SOURCE = ROOT / "test_route_master_completion_v6_7_2_2.py"
TEST_TARGET = ROOT / "tests" / "test_route_master_completion_v6_7_2_2.py"

for path in (SOURCE, TARGET_PARSER, TEST_SOURCE):
    if not path.exists():
        raise SystemExit(f"找不到文件: {path}")

root_backup = ROOT / "dev" / "v6.7" / "backups" / "route_builder_V6_7_pre_2_2.py.bak"
parser_backup = ROOT / "dev" / "v6.7" / "backups" / "parser_route_builder_pre_2_2.py.bak"

# Keep V6.7 development artifacts out of the root directory.
root_backup.parent.mkdir(parents=True, exist_ok=True)

def backup_once(src: Path, dst: Path) -> None:
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)

backup_once(TARGET_ROOT, root_backup)
backup_once(TARGET_PARSER, parser_backup)

shutil.copy2(SOURCE, TARGET_ROOT)
shutil.copy2(SOURCE, TARGET_PARSER)
TEST_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(TEST_SOURCE, TEST_TARGET)

print("MetroGIS V6.7-2.2 installed successfully.")
print(f"root   : {TARGET_ROOT}")
print(f"parser : {TARGET_PARSER}")
print(f"test   : {TEST_TARGET}")
print(f"backup : {root_backup}")
print("Overpass.py was not modified.")
