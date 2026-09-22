# MetroGIS V6.7-2.2

Route Master Station Completion

## 目标
在 V6.7-2 / V6.7-2.1 的 Route Master 基础上，对 Main Relation 的声明起终点与实际 stop sequence 做一致性修复。

只允许使用同一 Identity Cohort 中已有 Relation 的连续站序作为证据，补齐缺失的首端/末端站。

不做：
- 不修改 Overpass API
- 不硬编码广州 3 号线
- 不做全线路站点 union
- 不重排 Main 内部已有站序
- 不凭空生成站点

## 安装

```bash
cd /workspaces/MetroGIS
pytest -q -s test_route_master_completion_v6_7_2_2.py
python apply_v6_7_2_2_route_master_completion.py
```

## 广州实战

```bash
pytest -q -s test_guangzhou_line3_v6_7_2_2.py
```

## 预期

广州 3 号线当前实测中，Main Relation `9841061` 的 name 声明为 `机场北 → 海傍`，而 stop sequence 起止分别落在 `高增` / `海涌路`。V6.7-2.2 应通过同一 Cohort 的其他 Relation 证据补齐两个缺失端点，形成完整 Main station sequence。
