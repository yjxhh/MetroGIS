"""Install MetroGIS V6.7-1.1 exact Relation Identity fix.

This installer intentionally uses the root-level ``route_builder_V6_7.py``
as the source file, so no extra V6_7_1_1 source file is required.

Required files in the repository root:
  - route_builder_V6_7.py   (the supplied V6.7-1.1 fixed version)
  - test_relation_identity_selection_v6_7_1_1.py
  - this installer
"""

from pathlib import Path
import shutil

ROOT = Path.cwd()
SOURCE = ROOT / "route_builder_V6_7.py"
TARGET_PARSER = ROOT / "metrogis/parser/route_builder.py"
TEST_SOURCE = ROOT / "test_relation_identity_selection_v6_7_1_1.py"
TEST_TARGET = ROOT / "tests/test_relation_identity_selection_v6_7_1_1.py"
BACKUP_ROOT = ROOT / "route_builder_V6_7.py.v6_7_pre_1_1.bak"
BACKUP_PARSER = ROOT / "metrogis/parser/route_builder.py.v6_7_pre_1_1.bak"


def backup_once(src: Path, dst: Path) -> None:
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)


if not SOURCE.exists():
    raise SystemExit(
        f"找不到 V6.7-1.1 修复版: {SOURCE}\n"
        "请先用本次提供的 route_builder_V6_7.py 覆盖仓库根目录中的同名文件。"
    )

if not TARGET_PARSER.exists():
    raise SystemExit(f"找不到 parser route_builder.py: {TARGET_PARSER}")

if not TEST_SOURCE.exists():
    raise SystemExit(
        f"找不到回归测试: {TEST_SOURCE}\n"
        "请先上传 test_relation_identity_selection_v6_7_1_1.py。"
    )

source_text = SOURCE.read_text(encoding="utf-8")
required = (
    "def _line_identity_key(",
    "def _relation_identity_matches(",
    "Relation 精确线路身份过滤",
)
missing = [item for item in required if item not in source_text]
if missing:
    raise SystemExit(
        "当前 route_builder_V6_7.py 不是 V6.7-1.1 修复版，缺少: "
        + ", ".join(missing)
        + "\n请重新上传本次提供的完整 route_builder_V6_7.py。"
    )

backup_once(SOURCE, BACKUP_ROOT)
backup_once(TARGET_PARSER, BACKUP_PARSER)

# Root file is already the fixed reference version; install it into parser.
shutil.copy2(SOURCE, TARGET_PARSER)
TEST_TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(TEST_SOURCE, TEST_TARGET)

print("MetroGIS V6.7-1.1 exact Relation Identity fix installed.")
print(f"source  : {SOURCE}")
print(f"parser  : {TARGET_PARSER}")
print(f"test    : {TEST_TARGET}")
print(f"backup1 : {BACKUP_ROOT}")
print(f"backup2 : {BACKUP_PARSER}")
print("Overpass.py was intentionally not rewritten.")
