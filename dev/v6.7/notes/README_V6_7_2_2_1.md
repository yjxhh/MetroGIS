# MetroGIS V6.7-2.2.1

## 目的
修复 V6.7-2.2 在广州 3 号线实际数据中的端点补全失败。

### 问题
Main Relation 9841061 声明：

`机场北 → 海傍`

但实际 stop sequence：

`高增 → ... → 海涌路`

V6.7-2.2 只在其他 Relation 的实际 stop sequence 中寻找缺失端点，因此无法补全 `机场北` 与 `海傍`。

### 修复
V6.7-2.2.1 新增两类证据：

1. `actual_sequence`
   - 另一个同 Identity Cohort Relation 的实际 stop sequence 同时包含目标端点和 Main 当前端点。
2. `declared_endpoint`
   - 另一个同 Identity Cohort Relation 通过 `from=/to=` 或 Relation name 声明目标端点，且其实际 stop sequence 正好从/到 Main 当前端点。
   - 此模式只补 1 个缺失端点，不复制整段站序。

## 安装

将本目录文件放到 `/workspaces/MetroGIS/`：

```bash
cd /workspaces/MetroGIS
pytest -q -s test_route_master_completion_v6_7_2_2_1.py
python apply_v6_7_2_2_1_route_master_completion.py
pytest -q -s test_guangzhou_line3_v6_7_2_2_1.py
```

## 安全性

- 不修改 `metrogis/api/overpass.py`
- 不修改 YAML
- 不做城市/线路硬编码
- 内部缺站暂不自动补齐，只处理首尾端点
- 安装器只覆盖当前 V6.7 根版本与 parser，并保留一次备份
