#!/usr/bin/env python3
"""Install MetroGIS V6.7-2.2.2 completion-metric normalization."""
from __future__ import annotations
from pathlib import Path
import shutil

ROOT = Path.cwd()
SOURCE = ROOT / "route_builder_V6_7_2_2_2.py"
TARGET_ROOT = ROOT / "route_builder_V6_7.py"
TARGET_PARSER = ROOT / "metrogis/parser/route_builder.py"
TEST_SOURCE = ROOT / "test_route_master_quality_v6_7_2_2_2.py"
TEST_TARGET = ROOT / "tests/test_route_master_quality_v6_7_2_2_2.py"

if not SOURCE.exists():
    raise SystemExit(f"找不到 V6.7-2.2.2 源文件: {SOURCE}")
if not TARGET_PARSER.exists():
    raise SystemExit(f"找不到 parser route_builder.py: {TARGET_PARSER}")
if not TEST_SOURCE.exists():
    raise SystemExit(f"找不到回归测试: {TEST_SOURCE}")

BACKUP_DIR = ROOT / "dev/v6.7/backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

root_backup = BACKUP_DIR / "route_builder_V6_7_pre_2_2_2.py.bak"
parser_backup = BACKUP_DIR / "route_builder_parser_pre_2_2_2.py.bak"

if not root_backup.exists():
    shutil.copy2(TARGET_ROOT, root_backup)
if not parser_backup.exists():
    shutil.copy2(TARGET_PARSER, parser_backup)

shutil.copy2(SOURCE, TARGET_ROOT)
shutil.copy2(SOURCE, TARGET_PARSER)
TEST_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(TEST_SOURCE, TEST_TARGET)

print("MetroGIS V6.7-2.2.2 installed successfully.")
print(f"root   : {TARGET_ROOT}")
print(f"parser : {TARGET_PARSER}")
print(f"test   : {TEST_TARGET}")
print(f"backup : {root_backup}")
print(f"backup : {parser_backup}")
print("Overpass.py was not modified.")
