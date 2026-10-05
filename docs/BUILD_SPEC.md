# Build spec: live predictive maintenance on Databricks

All data in this repo is synthetic. No customer data is used.

## Environment

| Item | Value |
|---|---|
| Workspace | `fevm-serverless-stable-am1uc2` (AWS us-east-2, id 7474651880045550) |
| Catalog | `serverless_stable_am1uc2_catalog` (bundle variable `catalog`) |
| Zerobus endpoint | `7474651880045550.zerobus.us-east-2.cloud.databricks.com` |
| Zerobus identity | SP `pdm-zerobus-producer`, secret in scope `pdm-demo` |

## Unity Catalog layout

| Schema | Purpose | Key objects |
|---|---|---|
| `pdm_raw` | Landing + reference | `sensor_readings` (Zerobus target), `station_master`, `technicians`, `maintenance_events_history` |
| `pdm_core` | SDP output (silver/gold) | `sensor_readings_clean`, `station_features`, `station_risk_scores`, `station_health_current`, `maintenance_events` |
| `pdm_ml` | Models + training sets | `training_features`, model `station_failure_model@champion` |
| `pdm_ops` | Ops + semantic layer | `work_orders` (from Lakebase), metric views `station_reliability_metrics`, `work_order_metrics` |

## Asset model

3 plants x 4 lines x 8 stations = 96 stations. Station types: `press`, `cnc_mill`, `welder`, `robot_arm`, `conveyor`.

Sensors (1 Hz per station): `vibration_rms` (mm/s), `bearing_temp_c`, `motor_current_a`, `spindle_rpm`, `hydraulic_pressure_bar`, `acoustic_db`, `cycle_time_s`.

## Degradation physics (shared by backfill and live simulator)

Each station has a hidden health `h` in [0, 1]. A degradation episode starts at random (or on fault injection). `h` decays to 0 over 4 to 10 minutes. Degradation `d = 1 - h` drives one failure-mode signature:

| Mode | Station types | Signature |
|---|---|---|
| `bearing_wear` | cnc_mill, conveyor, robot_arm | vibration up (quadratic), acoustic up, temp slightly up |
| `overheating` | welder, robot_arm, cnc_mill | temp up strongly, current up |
| `seal_leak` | press | hydraulic pressure down, cycle time up |

At `h = 0` the station fails and stops for 60 s. A repair event resets `h = 1`. Benign load changes and noise spikes keep the problem non-trivial.

Time compression: 1 demo minute is roughly 1 real operating hour. The label horizon is 5 minutes ("next shift" in demo time).

## Features (one shared definition: `src/pdm/features.py`)

Sliding window 2 min, slide 10 s, per station. For each sensor: mean, std, max (min for pressure), plus deviation from the station-type nominal. Used identically by training (batch) and SDP (streaming).

## Model

`sklearn` HistGradientBoostingClassifier. Label: failure within the next 300 s after the window end. Metrics: PR-AUC, recall at 10% alert rate. It is registered in UC as `pdm_ml.station_failure_model` with alias `champion`. It is scored in-stream inside SDP and served on endpoint `pdm-station-risk` for what-if requests.

## Latency path

Simulator -> Zerobus -> `pdm_raw.sensor_readings` -> SDP continuous (silver, features, scores, AUTO CDC current state) -> Lakebase synced tables (continuous) -> FastAPI app (2 s polling). Target: 10 to 30 s event-to-screen. Measured and committed in `evidence/`.

## Lakebase

| Table | Kind | Purpose |
|---|---|---|
| `station_health_current` | Synced (continuous) | App grid |
| `station_risk_scores` | Synced (continuous) | App drill-down trend |
| `work_orders` | Native OLTP | Created in app |
| `sim_commands` | Native OLTP | Fault injection, read by simulator |

## Genie agent

Sources: metric views, `station_health_current`, `station_risk_scores`, `maintenance_events`, `station_master`, `work_orders`. With curated instructions, example SQL and a benchmark set. Benchmark results are committed as text.

## Repo layout

```
databricks.yml, resources/       Bundle (jobs, pipeline, serving, app)
src/pdm/                         Shared Python: config, physics, features
src/notebooks/                   Setup, backfill, training, Genie, evidence notebooks
src/pipeline/                    SDP pipeline source
src/simulator/                   Zerobus producer (live)
src/app/                         FastAPI app
tools/                           Evidence export helpers
evidence/                        Executed notebooks (.ipynb with outputs), run logs, query results
```

## Execution evidence

Every milestone commits text artifacts to `evidence/`:
- Notebooks run as Databricks jobs and are exported with outputs (`.ipynb` + `.md`).
- Job and pipeline run metadata (run ids, states, durations) as JSON.
- Query results (row counts, latency measurements, scores) as text tables.
- Real model output (metrics, sample predictions, serving responses).
- Genie benchmark questions, generated SQL and answers.
- App API responses (curl output).
