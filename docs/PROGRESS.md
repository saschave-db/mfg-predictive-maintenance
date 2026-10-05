# Build progress (paused 2026-10-05)

Workspace profile `fevm-serverless-stable-am1uc2`. Bundle target `demo`. All data synthetic.

## Done

| # | Step | State | Evidence |
|---|---|---|---|
| 0 | UC schemas `pdm_raw/core/ml/ops/live`, Zerobus bronze table, station master, technicians | Done (demo target run 244861711068746) | Not yet exported for the demo-target run |
| 1 | Zerobus SP `pdm-zerobus-producer` + secret scope `pdm-demo`, table grants | Done | In setup notebook |
| 2 | Zerobus simulator (serverless job, 96 stations at 1 Hz, 3 gateway streams) | Works; ~96 rec/s, ACK p50 60-200 ms; fault injection works | Earlier smoke log was deleted with the dev target; re-export needed |
| 3 | History backfill (24 h, 8.29M rows, ~1,100 failures) | Done on demo target (run 552116966031272) | Not yet exported |
| 4 | Model training + UC registry `@champion` | Done on demo target (finished 15:40). First run: PR-AUC 0.91, 271/271 failures detected, median lead 244 s. **New version (likely v2) is `@champion` now** | Not yet exported |
| 5 | SDP continuous pipeline (`pdm_live_pipeline`, id b5544be9-b72f-4e83-b029-1a7151fc53c1) | Running continuously with the OLD code (separate features hop, model v1) | - |
| 6 | Lakebase project `pdm-demo`, OLTP tables `pdm_ops.work_orders`, `pdm_ops.sim_commands` | Done | - |
| 7 | Lakehouse Sync Postgres `pdm_ops` -> UC `pdm_ops.lb_*_history` | Done | - |
| 8 | Governance + metric views (3 metric views, work_orders_current view, PII mask, row filter) | Done (run 50596819223088). Tags failed: governed tag policy; fixed in code (`pdm_` keys), not re-run | `evidence/05_governance_semantic/` |
| 9 | Genie agent "Plant Maintenance Agent" | Created, space id `01f1c10d662111078cd7326dff1774c6` | Benchmark not run yet |
| 10 | App code (FastAPI + JS), serving + app bundle resources | Written, validated, NOT deployed | - |

## Local code changes not yet deployed or committed

- Pipeline: features + scoring merged into `02_station_risk_scores.py`, `expect_or_drop(n_readings >= 110)`, files renumbered.
- Governance notebook: `pdm_`-prefixed tag keys.
- Bundle: `resources/serving.yml`, `resources/app.yml`, `resources/evidence.job.yml`, variables `model_version`, `genie_space_id`, `warehouse_id`.
- Last commit pushed: milestone 0 only. Everything else is uncommitted.

## Still running in the workspace (costs money)

- Simulator job run `320983066504714` (3 h, started ~15:27 PT): `databricks jobs cancel-run 320983066504714 --profile fevm-serverless-stable-am1uc2`
- Continuous pipeline: `databricks pipelines stop b5544be9-b72f-4e83-b029-1a7151fc53c1 --profile fevm-serverless-stable-am1uc2`
- Lakebase endpoint scales to zero on its own.
- Synced tables were deleted on purpose (to be recreated after the pipeline refresh).

## Next steps (in order)

1. Set `model_version` to the new `@champion` version; `databricks bundle deploy`.
2. Full refresh `station_risk_scores` + `station_health_current` (new flow shape): `databricks pipelines start-update <id> --full-refresh-selection station_risk_scores,station_health_current`.
3. Recreate the 2 continuous synced tables into `serverless_stable_am1uc2_catalog.pdm_live` (commands in session history / BUILD_SPEC).
4. Re-run governance job (tags).
5. Deploy app (`bundle run pdm_app`), grant the app SP: Lakebase SELECT on `pdm_live`, INSERT/UPDATE on `pdm_ops`; UC SELECT on Genie sources; Genie CAN_RUN.
6. Run Genie benchmark: `uv run --with databricks-sdk python tools/genie_benchmark.py --space-id 01f1c10d662111078cd7326dff1774c6 --out evidence/07_genie/benchmark.md`.
7. End-to-end evidence: inject fault via app API (curl, save JSON), then run `pdm_live_evidence` job and export.
8. Export evidence for setup/backfill/train/simulator runs with `tools/export_run.py`.
9. README with architecture, deploy steps, evidence index; commit and push (show Isaac /review tip before push).
