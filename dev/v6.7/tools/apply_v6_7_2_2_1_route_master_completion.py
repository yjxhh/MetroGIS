"""Install MetroGIS V6.7-2.2.1 Route Master endpoint completion fix.

V6.7-2.2.1 fixes endpoint completion when the declared Route Relation terminal
is missing from the actual stop members but is still declared by from=/to= or
encoded in the relation name.
"""

from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path.cwd()
SOURCE = ROOT / "route_builder_V6_7_2_2_1.py"
TARGET_ROOT = ROOT / "route_builder_V6_7.py"
TARGET_PARSER = ROOT / "metrogis/parser/route_builder.py"
TEST_SOURCE = ROOT / "test_route_master_completion_v6_7_2_2_1.py"
TEST_TARGET = ROOT / "tests/test_route_master_completion_v6_7_2_2_1.py"

for path in (SOURCE, TARGET_PARSER, TEST_SOURCE):
    if not path.exists():
        raise SystemExit(f"找不到: {path}")

backup_dir = ROOT / "dev/v6.7/backups"
backup_dir.mkdir(parents=True, exist_ok=True)
backup = backup_dir / "route_builder_V6_7_pre_2_2_1.py.bak"
if not backup.exists() and TARGET_ROOT.exists():
    shutil.copy2(TARGET_ROOT, backup)

shutil.copy2(SOURCE, TARGET_ROOT)
shutil.copy2(SOURCE, TARGET_PARSER)
TEST_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(TEST_SOURCE, TEST_TARGET)

print("MetroGIS V6.7-2.2.1 installed successfully.")
print(f"root   : {TARGET_ROOT}")
print(f"parser : {TARGET_PARSER}")
print(f"test   : {TEST_TARGET}")
print(f"backup : {backup}")
print("Overpass.py was not modified.")
