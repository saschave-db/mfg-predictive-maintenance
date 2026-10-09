# Live predictive maintenance for manufacturing on Databricks

An end-to-end demo for **Volta Industrial**, a fictional Tier-1 automotive supplier. It builds aluminum EV battery enclosures (trays, covers, cooling plates) for three OEMs and ships them just-in-sequence from 12 lines in three plants. If a station is down longer than the line's JIS buffer, the OEM's assembly line stops and Volta pays a line-stop charge. Plant gateways stream station telemetry through **Lakeflow Connect Zerobus**. **Spark Declarative Pipelines** clean it, build features and score failure risk in-stream with a **Unity Catalog** model. **Lakebase** serves the live state to a **Databricks App** and stores work orders. A **Genie agent** answers questions over governed **metric views**.

All data is synthetic, and Volta Industrial is a fictional customer. No real customer data is used.

**Business presentation:** [`presentation/deck.md`](presentation/deck.md). It covers the outcome, the KPI impact, the value model, and the pilot plan for Volta's COO (executive sponsor) and Head of Maintenance & Reliability (domain owner).

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
   '-- Model Serving pdm-station-risk via AI Gateway (usage tracking) --> app what-if

App --> Lakebase pdm_ops.work_orders / sim_commands --> Lakehouse Sync --> UC pdm_ops.lb_*_history --> Genie
```

## Requirement → source → live evidence

Every requirement maps to the code that implements it and to **executed output** that proves it ran. "E0x" are the executed evidence notebooks in `evidence/10_evidence_notebooks/` (`.md` is readable, `.ipynb` has the same outputs). Nothing here is a screenshot or prose: every evidence cell is captured output.

| # | Requirement | Source file(s) | Live evidence (captured output) |
|---|---|---|---|
| R1 | Synthetic data generation with realistic failure signatures | `src/pdm/physics.py`, `src/notebooks/01_backfill_history.py` | `03_backfill/01_backfill_history.md` (8.29M rows, failures per type); E01 §6 (degrading stations in raw data) |
| R2 | Lakeflow Connect **Zerobus** ingestion | `src/simulator/zerobus_producer.py`, `resources/simulator.job.yml`, `src/notebooks/00_setup_uc.py` | E01 §1 (job, serverless env), §2 (SP grants), §3 (**every data commit `engineInfo = Zerobus`**, cadence), §4 (rows/s per gateway); `02_zerobus_simulator/zerobus_producer.log` (ACK latency) |
| R3 | **SDP** ETL, continuous, with data quality | `src/pipeline/*.py`, `resources/pipeline.yml` | E02 §1 (deployed spec, `continuous=true`), §2 (flow states), §3 (expectation pass/drop counts), §4 (freshness per table) |
| R4 | Code that runs = code in repo | `evidence/source_snapshot/` (byte-identical copy + `SHA256SUMS`), `tools/snapshot_source.py` | E09 §2 (SHA-256 of **deployed** files = committed), §3 (full deployed pipeline source) |
| R5 | **Unity Catalog** governance: least privilege, masks, row filter, tags, lineage | `src/notebooks/03_governance_semantic.py`, `src/setup/app_uc_grants.sql` | E05 §1 grants, §2 masks/filter, **§2b enforcement on the app's service principal (non-owner): 6 of 18 rows, PII redacted, confirmed in query history**; `08_app/governance_as_app_sp.json` (raw responses of a control run: SP granted PLT-N → 6 rows; PLT-S added to `plant_access` → 12 rows; revoked → 6 rows); E02 §7 lineage |
| R6 | **ML** model, registered in UC, scored in-stream | `src/notebooks/02_train_model.py`, `src/pipeline/02_station_risk_scores.py` | `04_training/02_train_model.md` (PR-AUC 0.91, 271/271 failures, lead time); E03 §1–2 (versions, alias, metrics), §3 (pipeline = registry = serving) |
| R7 | **Model Serving** real call, through **AI Gateway** (usage tracking) | `resources/serving.yml` (`ai_gateway`), `src/app/app.py` (`/api/whatif` posts to the gateway invocations URL) | E03 §4 (**raw HTTP request + response**), §5 (gateway config + tracked requests from `system.serving.endpoint_usage`); `08_app/whatif_via_ai_gateway.md` (raw app responses with `gateway_url`) |
| R8 | **Genie agent** on metric views + work orders, with benchmarks | `src/genie/space_config.py`, `tools/genie_deploy.py`, metric views in `03_governance_semantic.py` | E06 §1 (deployed config), §2 (**raw Genie API response**, 10/10 vs reference SQL); `07_genie/benchmark.md` and `_run1_before_fixes.md` |
| R9 | **Lakebase**: OLTP, synced table, sync back to UC | `src/lakebase/*.sql`, `src/app/db.py` | E04 §2–4 (tables, grants, synced table status, Delta vs Postgres freshness), §5 (app query + plan), §6 (Lakehouse Sync CDC), **§7 (timed DB write/read round trips)** |
| R10 | **Databricks App** with actions | `src/app/*`, `resources/app.yml` | E07 (status, resources, deployments, writes); `08_app/e2e_fault_injection.md` (every API call through the app, with timings) |
| R11 | **Low-latency live probability** of maintenance need | all of the above | E02 §5 (per-hop latency); E08 (fault → HIGH in Delta and Postgres, repair → NORMAL); `06_live_pipeline/04_live_evidence.md` |
| R12 | Synthetic data only | `src/pdm/physics.py`, `00_setup_uc.py` (`example-mfg.test` emails, `+1-555` phones) | E00 (UC objects); E05 §2 (masked PII) |
| R13 | Industry fit: risk expressed in OEM delivery exposure (JIS buffer, line-stop charge, vehicle program, process step) | `src/notebooks/05_industry_context.py`, `resources/industry_context.job.yml`, `src/genie/space_config.py` | `11_industry_context/05_industry_context.md` (OEM programs, process steps, live exposure per line and per OEM); `07_genie/benchmark.md` (OEM exposure questions pass) |

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
| Genie benchmark | 12/12 graded questions match reference SQL, including 2 OEM delivery exposure questions (the earlier 10-question set was reproduced live in E06) | `07_genie/benchmark.md`, `10_evidence_notebooks/E06_genie.md` |
| OEM delivery exposure | An unplanned failure (112 min) outlasts every JIS buffer (45 to 90 min): about 44 min of OEM line stop, about $595k contract charge on average (synthetic terms) | `11_industry_context/05_industry_context.md` |
| Writer of the bronze table | 1,157 commits, all `engineInfo = Zerobus`, one every 5.0 s | `10_evidence_notebooks/E01_zerobus_ingestion.md` |
| Delta to Lakebase sync | Delta commit synced to Postgres in about 4 s | `09_deployed_resources/lakebase_synced_table.json` |
| Score consistency | Pipeline, registry model and Model Serving agree (max diff 0.00005, rounding) | `10_evidence_notebooks/E03_ml_model.md` |
| Notebook-driven E2E loop | Fault to HIGH in Delta and Postgres 367 s; repair to NORMAL 90 s; station never went down | `10_evidence_notebooks/E08_end_to_end.md` |
| Row filter on a non-owner identity | App SP sees 6 of 18 rows (Plant North), 12 after granting Plant South, 6 after revoking; PII redacted; confirmed in `system.query.history` | `08_app/governance_as_app_sp.json`, `10_evidence_notebooks/E05_governance.md` §2b |
| Raw Model Serving call | POST in 77 ms, response equals the pipeline score | `10_evidence_notebooks/E03_ml_model.md` §4 |
| AI Gateway usage tracking | 3 app what-if calls recorded in `system.serving.endpoint_usage` as the app SP, status 200 (system table lags about 15 to 20 min) | `10_evidence_notebooks/E03_ml_model.md` §5, `08_app/whatif_via_ai_gateway.md` |
| Lakebase round trip from a notebook | INSERT + SELECT 11.7 to 13.8 ms each | `10_evidence_notebooks/E04_lakebase.md` §7 |
| Deployed code = repo code | SHA-256 of every deployed pipeline file equals the committed snapshot | `10_evidence_notebooks/E09_source_integrity.md` |

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
| `E05_governance` | Grants, masks, row filter, tags, metric view YAML, KPI queries; enforcement on the app SP (non-owner) via query history |
| `E06_genie` | Deployed agent config, live benchmark with Genie SQL vs reference SQL, sample answers |
| `E07_app` | App status, resources, deployments, API call attempt, the app's writes in Lakebase and UC |
| `E08_end_to_end` | Live loop driven from the notebook: fault, alert in Delta and Postgres, work order, repair, recovery |
| `E09_source_integrity` | SHA-256 of deployed files vs committed snapshot, full deployed pipeline source |

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
| `evidence/11_industry_context/` | OEM programs and JIS terms per line, enclosure process steps, live OEM delivery exposure |

## Repo layout

```
databricks.yml, resources/   Declarative Automation Bundle: jobs, pipeline, serving endpoint, app
src/pdm/                     Shared Python: config, physics simulator, feature definition
src/simulator/               Zerobus producer (serverless job)
src/pipeline/                SDP pipeline sources
src/notebooks/               Setup, backfill, training, governance + metric views, live evidence, industry context
src/lakebase/                Postgres DDL and app grants
src/setup/                   UC grants for the app service principal
src/genie/                   Genie agent as code (instructions, example SQL, benchmarks)
src/app/                     FastAPI backend + static JS front end
tools/                       Evidence export, Genie deploy and benchmark, Lakebase SQL, E2E script
docs/                        Build spec, progress log
presentation/                Business deck (Markdown, Marp-compatible slides)
```

## Deploy

Prerequisites: a serverless workspace with Zerobus and Lakebase, Databricks CLI with a profile, and `uv` locally.

1. Create the Zerobus service principal and a secret scope `pdm-demo` with keys `zerobus_client_id`, `zerobus_client_secret`. Set the bundle variables in `databricks.yml` (catalog, SP app id, Zerobus endpoint).
2. `databricks bundle deploy`, then run `pdm_setup`, `pdm_backfill`, `pdm_train` in order.
3. Create the Lakebase project `pdm-demo`, run `src/lakebase/01_oltp_schema.sql` (`python tools/pg.py -f ...`), and create the Lakehouse Sync config for Postgres schema `pdm_ops`.
4. Set `model_version` to the `@champion` version, deploy again. Start the simulator job. The continuous pipeline starts on deploy.
5. Create the continuous synced table `pdm_live.station_risk_scores` (PK `station_id, window_end`).
6. Run `pdm_governance` and `pdm_industry_context`. Create the Genie agent with `tools/genie_deploy.py`, set `genie_space_id`, deploy.
7. `databricks bundle run pdm_app`. Apply `src/setup/app_uc_grants.sql` and `src/lakebase/02_app_grants.sql` for the app service principal.
8. Evidence: `tools/genie_benchmark.py`, `tools/e2e_demo.py`, job `pdm_live_evidence`, `tools/export_run.py <run_id> <dir>`.

## Known limitations

- **Sensor-to-screen is about 60 s, not the 10 to 30 s first planned.** Ingest takes about 5 s. The 2-minute sliding window waits for its watermark and stateful micro-batches (about 35 s). Sync and polling add the rest. Failures develop over 4 to 10 minutes and the model warns about 4 minutes ahead, so this is still actionable. We chose to accept and document it.
- Recovery after a repair takes about 3 minutes in the app. The 2-minute window must fill with post-repair data first.
- The serving endpoint scales to zero. The first what-if after idle took 62 s (cold start).
- "Top signal" is a simple explanation: the sensor deviating most from its nominal value. It is not SHAP.
- Genie answers and app queries run as the app service principal. Row filters therefore apply to the app's identity (proven: Plant North only), not per end user. Per-user filtering would need on-behalf-of-user auth.
- See `docs/BUILD_SPEC.md` for every deviation from the original plan and why.
