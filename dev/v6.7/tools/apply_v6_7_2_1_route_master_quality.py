"""Install MetroGIS V6.7-2.1 Route Master quality normalization."""

from pathlib import Path
import shutil

ROOT = Path.cwd()
SOURCE = ROOT / "route_builder_V6_7_2_1.py"
TARGET_ROOT = ROOT / "route_builder_V6_7.py"
TARGET_PARSER = ROOT / "metrogis/parser/route_builder.py"
TEST_SOURCE = ROOT / "test_route_master_quality_v6_7_2_1.py"
TEST_TARGET = ROOT / "tests/test_route_master_quality_v6_7_2_1.py"

required = (SOURCE, TARGET_PARSER, TEST_SOURCE)
for path in required:
    if not path.exists():
        raise SystemExit(f"找不到必要文件: {path}")


def backup_once(src: Path, dst: Path) -> None:
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)


backup_once(TARGET_ROOT, ROOT / "route_builder_V6_7.py.v6_7_2_1.bak")
backup_once(TARGET_PARSER, TARGET_PARSER.with_suffix(".py.v6_7_2_1.bak"))

shutil.copy2(SOURCE, TARGET_ROOT)
shutil.copy2(SOURCE, TARGET_PARSER)
TEST_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(TEST_SOURCE, TEST_TARGET)

print("MetroGIS V6.7-2.1 installed successfully.")
print(f"root   : {TARGET_ROOT}")
print(f"parser : {TARGET_PARSER}")
print(f"test   : {TEST_TARGET}")
print("Backups were created only when they did not already exist.")
print("Overpass.py was not modified in V6.7-2.1.")
