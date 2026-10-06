# Live predictive maintenance for manufacturing on Databricks

An end-to-end demo. Plant gateways stream station telemetry through **Lakeflow Connect Zerobus**. **Spark Declarative Pipelines** clean it, build features and score failure risk in-stream with a **Unity Catalog** model. **Lakebase** serves the live state to a **Databricks App** and stores work orders. A **Genie agent** answers questions over governed **metric views**.

All data is synthetic. No customer data is used.

## Architecture

```
Simulator (96 stations, 1 Hz)  <-- polls Lakebase pdm_ops.sim_commands (fault injection / repair)
   | Zerobus Ingest SDK, 3 gateway streams
   v
UC pdm_raw.sensor_readings (managed Delta, bronze)
   | SDP pipeline, continuous, serverless
   |-- pdm_core.sensor_readings_clean   dedup (at-least-once), expectations, normalization
   |-- pdm_core.station_risk_scores     2-min sliding windows every 10 s + MLflow model @champion in-stream
   |-- pdm_core.station_health_current  AUTO CDC SCD1, latest state per station
   '-- pdm_core.maintenance_events      materialized view over the maintenance log
   |
   |-- Lakebase synced table (continuous) pdm_live.station_risk_scores --> FastAPI app (2 s polling)
   |-- Metric views pdm_ops.*_metrics --> Genie agent "Plant Maintenance Agent"
   '-- Model Serving pdm-station-risk (same UC model) --> app what-if

App --> Lakebase pdm_ops.work_orders / sim_commands --> Lakehouse Sync --> UC pdm_ops.lb_*_history --> Genie
```

## Why each piece

| Step | Product | Why it is here |
|---|---|---|
| Data generation | Python physics-lite simulator | Real plant data is never available for demos. A degradation model with distinct failure signatures gives the model real signal and Genie meaningful answers. |
| Ingestion | Lakeflow Connect Zerobus | Gateways push straight into a governed Delta table. No Kafka to run. |
| ETL | Spark Declarative Pipelines | Declarative streaming with data-quality expectations, lineage and recovery. One feature definition for training and scoring. |
| Governance | Unity Catalog | Lineage from Zerobus table to app, PII masks, row filters, tags, model registry, metric views. |
| ML | MLflow + UC model registry | Explainable failure probability, scored in-stream and served for what-if. |
| AI | Genie agent on metric views | Operations leaders ask questions in plain language over governed KPIs. |
| OLTP + serving | Lakebase | Millisecond reads for the app, transactional work orders, and changes flow back to UC. |
| Front end | Databricks App (FastAPI) | The live screen for the plant manager, with actions. |

## Measured results (from `evidence/`)

| What | Result | Source |
|---|---|---|
| Ingest rate | 95 to 100 rows/s from 96 stations, 3 Zerobus streams | `02_zerobus_simulator/zerobus_producer.log` |
| Zerobus durability ACK round trip | p50 86 to 190 ms | same |
| Sensor to silver (Zerobus + bronze + SDP) | p50 3.9 s, p95 7.7 s | `06_live_pipeline/04_live_evidence.md` |
| Sensor to risk score in Delta | p50 38 s, p95 43 s | same |
| Sensor to app screen | about 45 to 63 s data age | `08_app/e2e_fault_injection.md` |
| Lakebase query from the app | 4 to 32 ms | same |
| Model on a later held-out time window | PR-AUC 0.91, ROC-AUC 0.97, precision 0.95 / recall 0.80 at 0.7 | `04_training/02_train_model.md` |
| Failures detected before they happened | 271 of 271, median lead time 244 s (horizon 300 s) | same |
| Fault from app to simulator | applied 0.4 s after the click | `06_live_pipeline/04_live_evidence.md` |
| Injected fault to HIGH risk | 3 min 2 s in Delta, 3 min 47 s in the app | same, and `08_app/` |
| Model Serving what-if (warm) | 41 to 140 ms round trip | `08_app/whatif_warm.md` |
| Genie benchmark | 10/10 graded questions match reference SQL (reproduced live in E06) | `07_genie/benchmark.md`, `10_evidence_notebooks/E06_genie.md` |
| Writer of the bronze table | 1,157 commits, all `engineInfo = Zerobus`, one every 5.0 s | `10_evidence_notebooks/E01_zerobus_ingestion.md` |
| Delta to Lakebase sync | Delta commit synced to Postgres in about 4 s | `09_deployed_resources/lakebase_synced_table.json` |
| Score consistency | Pipeline, registry model and Model Serving agree (max diff 0.00005, rounding) | `10_evidence_notebooks/E03_ml_model.md` |
| Notebook-driven E2E loop | Fault to HIGH in Delta and Postgres 334 s; repair to NORMAL 75 s; station never went down | `10_evidence_notebooks/E08_end_to_end.md` |

Time is compressed: one demo minute is about one real operating hour.

## Evidence index

All evidence is text. Executed notebooks are exported from the Databricks job runs with their cell outputs (`.ipynb` and a readable `.md`).

**Start here: `evidence/10_evidence_notebooks/`.** One executed notebook per step (E00 to E08). Each one explains what was built, what it proves, and then shows the proof as live cell output: SDK calls, SQL on Unity Catalog, and SQL on Lakebase run from the notebook.

| Notebook | Proves |
|---|---|
| `E00_overview` | Architecture, step map, live state of every deployed resource |
| `E01_zerobus_ingestion` | Producer job, SP least privilege, Delta commits written by the Zerobus SP, throughput and freshness per gateway, duplicates |
| `E02_sdp_pipeline` | Deployed spec, update history, flow states, expectations, row counts, per-hop latency, UC lineage |
| `E03_ml_model` | UC versions and alias, MLflow metrics, in-stream scores reproduced with the registry model and Model Serving |
| `E04_lakebase` | Endpoint, Postgres tables, app-role grants, synced-table status, Delta vs Postgres freshness, query plan, Lakehouse Sync CDC |
| `E05_governance` | Grants, masks, row filter, tags, metric view YAML, KPI queries |
| `E06_genie` | Deployed agent config, live benchmark with Genie SQL vs reference SQL, sample answers |
| `E07_app` | App status, resources, deployments, API call attempt, the app's writes in Lakebase and UC |
| `E08_end_to_end` | Live loop driven from the notebook: fault, alert in Delta and Postgres, work order, repair, recovery |

The build notebooks and tool outputs:

| Folder | Contents |
|---|---|
| `evidence/01_setup/` | Schemas, Zerobus target table, reference data, SP grants |
| `evidence/02_zerobus_simulator/` | Producer stdout: streams opened, rates, ACK latency, app commands, failures |
| `evidence/03_backfill/` | 24 h labeled history (8.29M rows), maintenance log |
| `evidence/04_training/` | Training set, metrics, lead time per failure mode, UC registration |
| `evidence/05_governance_semantic/` | Metric views, masks, row filter, tags, KPI query results |
| `evidence/06_live_pipeline/` | Live throughput, per-hop latency, expectations, fault timeline |
| `evidence/07_genie/` | Benchmark before fixes (7/10) and after (10/10), with Genie SQL and results |
| `evidence/08_app/` | End-to-end run through the app API, warm serving calls |
| `evidence/09_deployed_resources/` | State of pipeline, synced table, serving endpoint, app, Genie space, Lakebase |

## Repo layout

```
databricks.yml, resources/   Declarative Automation Bundle: jobs, pipeline, serving endpoint, app
src/pdm/                     Shared Python: config, physics simulator, feature definition
src/simulator/               Zerobus producer (serverless job)
src/pipeline/                SDP pipeline sources
src/notebooks/               Setup, backfill, training, governance + metric views, live evidence
src/lakebase/                Postgres DDL and app grants
src/setup/                   UC grants for the app service principal
src/genie/                   Genie agent as code (instructions, example SQL, benchmarks)
src/app/                     FastAPI backend + static JS front end
tools/                       Evidence export, Genie deploy and benchmark, Lakebase SQL, E2E script
docs/                        Build spec, progress log
```

## Deploy

Prerequisites: a serverless workspace with Zerobus and Lakebase, Databricks CLI with a profile, and `uv` locally.

1. Create the Zerobus service principal and a secret scope `pdm-demo` with keys `zerobus_client_id`, `zerobus_client_secret`. Set the bundle variables in `databricks.yml` (catalog, SP app id, Zerobus endpoint).
2. `databricks bundle deploy`, then run `pdm_setup`, `pdm_backfill`, `pdm_train` in order.
3. Create the Lakebase project `pdm-demo`, run `src/lakebase/01_oltp_schema.sql` (`python tools/pg.py -f ...`), and create the Lakehouse Sync config for Postgres schema `pdm_ops`.
4. Set `model_version` to the `@champion` version, deploy again. Start the simulator job. The continuous pipeline starts on deploy.
5. Create the continuous synced table `pdm_live.station_risk_scores` (PK `station_id, window_end`).
6. Run `pdm_governance`. Create the Genie agent with `tools/genie_deploy.py`, set `genie_space_id`, deploy.
7. `databricks bundle run pdm_app`. Apply `src/setup/app_uc_grants.sql` and `src/lakebase/02_app_grants.sql` for the app service principal.
8. Evidence: `tools/genie_benchmark.py`, `tools/e2e_demo.py`, job `pdm_live_evidence`, `tools/export_run.py <run_id> <dir>`.

## Known limitations

- **Sensor-to-screen is about 60 s, not the 10 to 30 s first planned.** Ingest takes about 5 s. The 2-minute sliding window waits for its watermark and stateful micro-batches (about 35 s). Sync and polling add the rest. Failures develop over 4 to 10 minutes and the model warns about 4 minutes ahead, so this is still actionable. We chose to accept and document it.
- Recovery after a repair takes about 3 minutes in the app. The 2-minute window must fill with post-repair data first.
- The serving endpoint scales to zero. The first what-if after idle took 62 s (cold start).
- "Top signal" is a simple explanation: the sensor deviating most from its nominal value. It is not SHAP.
- Genie answers use the app service principal, so per-user row filters do not apply inside the app.
- See `docs/BUILD_SPEC.md` for every deviation from the original plan and why.
