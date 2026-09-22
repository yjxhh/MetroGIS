# MetroGIS V6.7-2.2.2

## 目的
修正 Route Master Completion 的统计口径。

旧版会把 Main 正向与反向两个方向的补站数量直接相加，导致：
- 实际 canonical Main 从 26 -> 28，仅新增 2 个站；
- 日志却显示 total_added_stops = 4。

V6.7-2.2.2 将指标明确分开：

- `unique_added_stops`: canonical Main 的净新增站点数
- `forward_added_stops`: Main 正向 Relation 补站数
- `reverse_added_stops`: Main 反向 Relation 补站数
- `directional_added_stops`: 正向+反向工作的总数量
- `total_added_stops`: 为兼容旧调用，改为 canonical/unique 口径

广州 3 号线预期：

```text
unique_added_stops     = 2
forward_added_stops    = 2
reverse_added_stops    = 2
directional_added_stops = 4
total_added_stops      = 2
```

## 安装
```bash
cd /workspaces/MetroGIS
pytest -q -s test_route_master_quality_v6_7_2_2_2.py
python apply_v6_7_2_2_2_route_master_metrics.py
pytest -q -s test_guangzhou_line3_v6_7_2_2_2.py
```
