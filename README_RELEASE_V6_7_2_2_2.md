# MetroGIS V6.7-2.2.2 Release

V6.7-2.2.2 is the stabilized Route Master completion-metrics release.

## Verified Guangzhou Line 3 result

```text
main relation          = 9841061
actual start           = 机场北
actual end             = 海傍
main station count     = 28
unique added stops     = 2
forward added stops    = 2
reverse added stops    = 2
directional added      = 4
legacy total_added     = 2
completion confidence  = 0.85
```

The canonical/net completion count is now separate from directional work, so
forward and reverse completion do not double-count the same terminal additions.

## Integration and cleanup

Copy the files in this package to `/workspaces/MetroGIS/`, then run:

```bash
cd /workspaces/MetroGIS
python apply_and_cleanup_v6_7_2_2_2.py
pytest -q
pytest -q -s tests/test_route_master_quality_v6_7_2_2_2.py
```

The Guangzhou Overpass test is preserved as a manual integration test under:

```text
dev/v6.7/manual_tests/manual_test_guangzhou_line3_v6_7_2_2_2.py
```

Run it when a live Overpass regression check is needed:

```bash
pytest -q -s dev/v6.7/manual_tests/manual_test_guangzhou_line3_v6_7_2_2_2.py
```

## Release

After the full suite passes:

```bash
git status
git add -A
git commit -m "Release V6.7-2.2.2: Route Master completion metrics"
git tag -a v6.7-2.2.2 -m "MetroGIS V6.7-2.2.2"
git push origin main --follow-tags
```

## Packaging fix in this clean release

The regression test loads the archived V6.7-2.2.2 snapshot from `dev/v6.7/versions/` (with a development fallback to `route_builder_V6_7.py`). Manual tests under `dev/v6.7/manual_tests/` are renamed to `manual_test_*.py` so a plain `pytest -q` does not auto-collect the manual archive. A `manual_tests/conftest.py` is created to add the repository root to `sys.path`, so archived manual tests remain explicitly runnable. The installer itself is also archived under `dev/v6.7/tools/` after execution.
