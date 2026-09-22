from pathlib import Path
import re
import shutil

ROOT = Path.cwd()
OVERPASS = ROOT / "metrogis/api/overpass.py"
ROUTE_BUILDER = ROOT / "metrogis/parser/route_builder.py"
NEW_ROUTE_BUILDER = ROOT / "route_builder_V6_7.py"

if not OVERPASS.exists():
    raise SystemExit(f"找不到: {OVERPASS}")
if not ROUTE_BUILDER.exists():
    raise SystemExit(f"找不到: {ROUTE_BUILDER}")
if not NEW_ROUTE_BUILDER.exists():
    raise SystemExit(
        "找不到 route_builder_V6_7.py。请先把 ChatGPT 提供的完整 V6.7 文件放到项目根目录。"
    )

# 备份当前文件，便于立即回滚。
shutil.copy2(OVERPASS, OVERPASS.with_suffix(".py.v6_6.bak"))
shutil.copy2(ROUTE_BUILDER, ROUTE_BUILDER.with_suffix(".py.v6_6.bak"))

# 只修改 Relation 名称标准化规则：同时支持 ASCII / 全角冒号。
s = OVERPASS.read_text(encoding="utf-8")
old = 'r":[^:]+$"'
new = 'r"[:：][^:：]+$"'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("没有找到 normalize_relation_name() 的目标正则，请不要自动覆盖 overpass.py。")
OVERPASS.write_text(s, encoding="utf-8")

# route_builder 使用完整的 V6.7 替换文件。
shutil.copy2(NEW_ROUTE_BUILDER, ROUTE_BUILDER)

print("V6.7 Relation Identity fix 已应用。")
print(f"备份: {OVERPASS.with_suffix('.py.v6_6.bak')}")
print(f"备份: {ROUTE_BUILDER.with_suffix('.py.v6_6.bak')}")
