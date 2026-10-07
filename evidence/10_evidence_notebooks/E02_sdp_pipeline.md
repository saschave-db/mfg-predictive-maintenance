# Executed notebook: E02_sdp_pipeline

Exported from Databricks job run `994447175034582` (task `E02_sdp_pipeline`, task run `474841913877680`).

Result: **SUCCESS** · start 2026-10-07T22:58:20.393000+00:00 · end 2026-10-07T22:58:59.479000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


# E02 · ETL with Lakeflow Spark Declarative Pipelines (continuous)

**What was built.** Pipeline `pdm_live_pipeline` (serverless, continuous) with four datasets:

| Dataset | Type | Logic |
|---|---|---|
| `sensor_readings_clean` | streaming table | Reads Zerobus bronze, watermark 30 s, `dropDuplicatesWithinWatermark(event_id)`, 6 drop expectations + 1 warn expectation, joins station nominals |
| `station_risk_scores` | streaming table | 2-minute sliding windows every 10 s (shared `pdm.features`), drops incomplete windows (`expect_or_drop n_readings >= 110`), scores in-stream with UC model `@champion` |
| `station_health_current` | streaming table (AUTO CDC SCD1) | Latest risk row per station |
| `maintenance_events` | materialized view | Maintenance log joined with station context |

**What this notebook proves.** The deployed spec, the update history, that every flow is running, data-quality
results from the event log, row counts and freshness per table, and column-level lineage captured by Unity Catalog.

```python
%pip install -q "databricks-sdk>=0.81" pg8000
%restart_python
```

Output:

```text
[43mNote: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.[0m
```

```python
from _helpers import *  # noqa: F401,F403
spark.sql(f"USE CATALOG {CATALOG}")
```

Output:

```text
{"text/plain": "DataFrame[]"}
```

## 1 · Deployed pipeline specification

```python
p = w.pipelines.get(PIPELINE_ID)
show({"name": p.name, "state": p.state.value, "continuous": p.spec.continuous, "serverless": p.spec.serverless,
      "photon": p.spec.photon, "catalog": p.spec.catalog, "schema": p.spec.schema, "channel": p.spec.channel,
      "libraries": [l.file.path.split("/files/")[-1] for l in p.spec.libraries],
      "environment": p.spec.environment.as_dict() if p.spec.environment else None})
```

Output:

```text
{
  "name": "pdm_live_pipeline",
  "state": "RUNNING",
  "continuous": true,
  "serverless": true,
  "photon": true,
  "catalog": "serverless_stable_am1uc2_catalog",
  "schema": "pdm_core",
  "channel": "CURRENT",
  "libraries": [
    "src/pipeline/01_sensor_readings_clean.py",
    "src/pipeline/02_station_risk_scores.py",
    "src/pipeline/03_station_health_current.py",
    "src/pipeline/04_maintenance_events.py"
  ],
  "environment": {
    "dependencies": [
      "scikit-learn==1.7.2",
      "mlflow>=3.1"
    ]
  }
}
```

## 2 · Update history and current flow states (event log)

```python
display(spark.sql(f"""
SELECT origin.update_id, min(timestamp) AS started, max(timestamp) AS last_event,
       max_by(details:update_progress.state::string, timestamp) FILTER (WHERE event_type = 'update_progress') AS last_state,
       first(details:create_update.cause::string, true) AS cause
FROM event_log('{PIPELINE_ID}') GROUP BY ALL ORDER BY started DESC LIMIT 8"""))
display(spark.sql(f"""
SELECT origin.flow_name AS flow, max_by(details:flow_progress.status::string, timestamp) AS latest_status, max(timestamp) AS at
FROM event_log('{PIPELINE_ID}') WHERE event_type = 'flow_progress' AND details:flow_progress.status IS NOT NULL
  AND origin.update_id = (SELECT max_by(origin.update_id, timestamp) FROM event_log('{PIPELINE_ID}'))
GROUP BY ALL ORDER BY flow"""))
```

Output:

| update_id | started | last_event | last_state | cause |
|---|---|---|---|---|
| 15457793-548f-4450-b098-9921172ec0d6 | 2026-10-07T22:49:10.667Z | 2026-10-07T22:58:20.222Z | RUNNING | API_CALL |
| cdea0609-67b3-486d-8b32-e2374e5f6f67 | 2026-10-06T16:55:58.758Z | 2026-10-06T18:52:25.654Z | CANCELED | API_CALL |
| d4c83445-9e51-4655-8121-b7c1bb7fff93 | 2026-10-06T16:50:46.348Z | 2026-10-06T16:55:27.346Z | CANCELED | RETRY_ON_FAILURE |
| 65fee8e5-67e7-41f9-9b51-39813aa71eeb | 2026-10-06T16:44:17.503Z | 2026-10-06T16:50:43.393Z | FAILED | RETRY_ON_FAILURE |
| 21171f70-870e-4c07-ba95-4e189797a920 | 2026-10-06T16:40:29.963Z | 2026-10-06T16:44:14.443Z | FAILED | RETRY_ON_FAILURE |
| f68002b3-c96d-454a-b347-dafbd158dfc1 | 2026-10-06T16:38:01.940Z | 2026-10-06T16:40:26.803Z | FAILED | RETRY_ON_FAILURE |
| 922af5d5-cc73-4535-8f3a-71f3b8506df1 | 2026-10-06T16:36:14.370Z | 2026-10-06T16:37:59.059Z | FAILED | RETRY_ON_FAILURE |
| b55d948e-ea39-44e8-85ea-4fbce51ccc44 | 2026-10-06T16:34:46.861Z | 2026-10-06T16:36:12.461Z | FAILED | RETRY_ON_FAILURE |

Output:

| flow | latest_status | at |
|---|---|---|
| serverless_stable_am1uc2_catalog.pdm_core.maintenance_events | RUNNING | 2026-10-07T22:58:19.427Z |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | RUNNING | 2026-10-07T22:58:20.221Z |
| serverless_stable_am1uc2_catalog.pdm_core.station_health_current | IDLE | 2026-10-07T22:58:05.723Z |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | RUNNING | 2026-10-07T22:57:41.642Z |

## 3 · Data-quality expectations (cumulative, current update)

```python
display(spark.sql(f"""
SELECT split(flow_name, '\\\\.')[2] AS dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed_or_dropped
FROM (SELECT origin.flow_name AS flow_name, explode(from_json(details:flow_progress.data_quality.expectations,
        'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x
      FROM event_log('{PIPELINE_ID}') WHERE event_type = 'flow_progress')
GROUP BY ALL ORDER BY dataset, expectation"""))
```

Output:

| dataset | expectation | passed | failed_or_dropped |
|---|---|---|---|
| sensor_readings_clean | current_in_range | 998784 | 0 |
| sensor_readings_clean | not_from_future | 998784 | 0 |
| sensor_readings_clean | pressure_in_range | 998784 | 0 |
| sensor_readings_clean | temperature_in_range | 998784 | 0 |
| sensor_readings_clean | valid_station | 998784 | 0 |
| sensor_readings_clean | valid_ts | 998784 | 0 |
| sensor_readings_clean | vibration_in_range | 998784 | 0 |
| station_risk_scores | complete_window | 80640 | 9504 |

## 4 · Row counts and freshness per table

```python
display(spark.sql("""
SELECT 'pdm_raw.sensor_readings (bronze, Zerobus)' AS table_name, count(*) AS rows, max(ts) AS newest, timestampdiff(SECOND, max(ts), current_timestamp()) AS seconds_behind FROM pdm_raw.sensor_readings
UNION ALL SELECT 'pdm_core.sensor_readings_clean (silver)', count(*), max(ts), timestampdiff(SECOND, max(ts), current_timestamp()) FROM pdm_core.sensor_readings_clean
UNION ALL SELECT 'pdm_core.station_risk_scores (gold)', count(*), max(window_end), timestampdiff(SECOND, max(window_end), current_timestamp()) FROM pdm_core.station_risk_scores
UNION ALL SELECT 'pdm_core.station_health_current (gold)', count(*), max(window_end), timestampdiff(SECOND, max(window_end), current_timestamp()) FROM pdm_core.station_health_current
UNION ALL SELECT 'pdm_core.maintenance_events (MV)', count(*), max(event_ts), NULL FROM pdm_core.maintenance_events"""))
```

Output:

| table_name | rows | newest | seconds_behind |
|---|---|---|---|
| pdm_raw.sensor_readings (bronze, Zerobus) | 866112 | 2026-10-07T22:58:39.000Z | 2 |
| pdm_core.sensor_readings_clean (silver) | 865632 | 2026-10-07T22:58:34.000Z | 7 |
| pdm_core.station_risk_scores (gold) | 80832 | 2026-10-07T22:57:00.000Z | 101 |
| pdm_core.station_health_current (gold) | 96 | 2026-10-07T22:57:00.000Z | 101 |
| pdm_core.maintenance_events (MV) | 2461 | 2026-10-05T20:59:47.000Z |  |

## 5 · Per-hop latency (last 10 minutes)

```python
display(spark.sql("""
SELECT 'sensor -> silver' AS hop, round(percentile((unix_millis(silver_at) - unix_millis(ts)) / 1000, 0.5), 1) AS p50_s,
       round(percentile((unix_millis(silver_at) - unix_millis(ts)) / 1000, 0.95), 1) AS p95_s
FROM pdm_core.sensor_readings_clean WHERE ts > current_timestamp() - INTERVAL 10 MINUTES
UNION ALL
SELECT 'sensor -> risk score', round(percentile((unix_millis(scored_at) - unix_millis(last_reading_ts)) / 1000, 0.5), 1),
       round(percentile((unix_millis(scored_at) - unix_millis(last_reading_ts)) / 1000, 0.95), 1)
FROM pdm_core.station_risk_scores WHERE window_end > current_timestamp() - INTERVAL 10 MINUTES"""))
```

Output:

| hop | p50_s | p95_s |
|---|---|---|
| sensor -> silver | 6.3 | 59.9 |
| sensor -> risk score | 63.2 | 119.3 |

## 6 · Sample output rows

```python
display(spark.sql("""SELECT station_id, window_start, window_end, n_readings, failure_probability, risk_band, top_signal,
                     top_signal_deviation_pct, round(avg_vibration_rms, 2) AS vib, round(avg_bearing_temp_c, 1) AS temp, model_uri
                     FROM pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 10"""))
```

Output:

| station_id | window_start | window_end | n_readings | failure_probability | risk_band | top_signal | top_signal_deviation_pct | vib | temp | model_uri |
|---|---|---|---|---|---|---|---|---|---|---|
| PLT-E-B02 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.9973 | HIGH | vibration_rms | 107.7 | 3.12 | 53.0 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-S-A04 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.9963 | HIGH | vibration_rms | 92.8 | 1.93 | 45.0 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-N-C07 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.9897 | HIGH | bearing_temp_c | 11.5 | 0.88 | 66.9 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-S-A06 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.7449 | HIGH | motor_current_a | 8.6 | 1.5 | 49.3 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-S-C01 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.2521 | NORMAL | vibration_rms | 13.1 | 2.26 | 43.4 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-E-D01 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.1995 | NORMAL | motor_current_a | 9.6 | 1.95 | 46.3 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-E-D07 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.1588 | NORMAL | spindle_rpm | 6.9 | 0.83 | 60.7 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-S-C04 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.1503 | NORMAL | spindle_rpm | 8.8 | 1.03 | 42.5 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-E-C04 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.1459 | NORMAL | cycle_time_s | 6.8 | 1.05 | 44.2 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |
| PLT-E-C02 | 2026-10-07T22:55:00.000Z | 2026-10-07T22:57:00.000Z | 120 | 0.1336 | NORMAL | cycle_time_s | 8.0 | 1.51 | 49.0 | models:/serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model@champion |

## 7 · Lineage captured by Unity Catalog
`system.access.table_lineage` records the table-to-table flow from the Zerobus landing table through the pipeline
to the Lakebase sync and metric views. (System-table lineage can lag by some minutes.)

```python
display(spark.sql(f"""
SELECT source_table_full_name, target_table_full_name, entity_type, max(event_time) AS last_seen, count(*) AS events
FROM system.access.table_lineage
WHERE (source_table_catalog = '{CATALOG}' AND source_table_schema LIKE 'pdm_%')
   OR (target_table_catalog = '{CATALOG}' AND target_table_schema LIKE 'pdm_%')
GROUP BY ALL ORDER BY source_table_full_name, target_table_full_name"""))
```

Output:

| source_table_full_name | target_table_full_name | entity_type | last_seen | events |
|---|---|---|---|---|
|  | serverless_stable_am1uc2_catalog.pdm_core.event_log_8684d777_546b_4574_bf10_e7002a59fe0d | PIPELINE | 2026-10-05T22:24:08.113Z | 6 |
|  | serverless_stable_am1uc2_catalog.pdm_core.event_log_b5544be9_b72f_4e83_b029_1a7151fc53c1 | PIPELINE | 2026-10-06T18:52:26.931Z | 292 |
|  | serverless_stable_am1uc2_catalog.pdm_live.event_log_5135c1d5_fce7_4893_898c_d902dc34a0ea | PIPELINE | 2026-10-06T18:52:34.686Z | 220 |
|  | serverless_stable_am1uc2_catalog.pdm_live.event_log_7857f2ec_f966_4dcb_9133_b3a9e4c4c0ea | PIPELINE | 2026-10-05T22:38:36.347Z | 11 |
|  | serverless_stable_am1uc2_catalog.pdm_live.event_log_8416b65a_8919_4648_95ef_fc6698d736ec | PIPELINE | 2026-10-05T22:38:45.446Z | 11 |
|  | serverless_stable_am1uc2_catalog.pdm_ml.history_readings | JOB | 2026-10-05T22:32:59.432Z | 2 |
|  | serverless_stable_am1uc2_catalog.pdm_raw.maintenance_events_history | JOB | 2026-10-05T22:37:48.384Z | 2 |
|  | serverless_stable_am1uc2_catalog.pdm_raw.sensor_readings | JOB | 2026-10-05T22:27:44.916Z | 2 |
|  | serverless_stable_am1uc2_catalog.pdm_raw.station_master | JOB | 2026-10-05T22:27:56.122Z | 2 |
|  | serverless_stable_am1uc2_catalog.pdm_raw.technicians | JOB | 2026-10-05T22:28:01.388Z | 2 |
| serverless_stable_am1uc2_catalog.pdm_core.event_log_b5544be9_b72f_4e83_b029_1a7151fc53c1 |  | JOB | 2026-10-06T17:42:53.259Z | 5 |
| serverless_stable_am1uc2_catalog.pdm_core.event_log_b5544be9_b72f_4e83_b029_1a7151fc53c1 |  | PIPELINE | 2026-10-06T16:56:10.291Z | 3 |
| serverless_stable_am1uc2_catalog.pdm_core.maintenance_events |  | JOB | 2026-10-06T17:43:01.467Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_core.maintenance_events | serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics | JOB | 2026-10-06T17:50:57.429Z | 16 |
| serverless_stable_am1uc2_catalog.pdm_core.maintenance_events | serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics |  | 2026-10-06T17:50:45.509Z | 27 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean |  |  | 2026-10-06T17:07:45.254Z | 3 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean |  | JOB | 2026-10-06T18:07:58.469Z | 5 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | PIPELINE | 2026-10-06T17:01:36.333Z | 3 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | serverless_stable_am1uc2_catalog.pdm_core.station_features | PIPELINE | 2026-10-05T22:45:28.302Z | 96 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | PIPELINE | 2026-10-06T18:52:16.783Z | 1225 |
| serverless_stable_am1uc2_catalog.pdm_core.station_features |  |  | 2026-10-05T22:32:32.245Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_core.station_features | serverless_stable_am1uc2_catalog.pdm_core.station_features | PIPELINE | 2026-10-05T22:41:44.763Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_core.station_features | serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | PIPELINE | 2026-10-05T22:45:28.399Z | 77 |
| serverless_stable_am1uc2_catalog.pdm_core.station_health_current |  |  | 2026-10-06T17:50:28.212Z | 54 |
| serverless_stable_am1uc2_catalog.pdm_core.station_health_current |  | PIPELINE | 2026-10-05T22:33:22.193Z | 5 |
| serverless_stable_am1uc2_catalog.pdm_core.station_health_current |  | JOB | 2026-10-06T17:50:38.180Z | 14 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores |  |  | 2026-10-06T17:07:47.318Z | 5 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores |  | PIPELINE | 2026-10-06T17:03:45.054Z | 10 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores |  | JOB | 2026-10-06T18:02:58.220Z | 31 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | serverless_stable_am1uc2_catalog.pdm_core.station_health_current | PIPELINE | 2026-10-06T16:57:59.036Z | 5 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | PIPELINE | 2026-10-06T17:08:01.354Z | 2 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | serverless_stable_am1uc2_catalog.pdm_ops.station_risk_metrics | JOB | 2026-10-06T17:46:20.867Z | 3 |
| serverless_stable_am1uc2_catalog.pdm_live.station_health_current |  | PIPELINE | 2026-10-05T22:33:27.849Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_live.station_risk_scores |  | PIPELINE | 2026-10-06T17:03:51.873Z | 2 |
| serverless_stable_am1uc2_catalog.pdm_ml.history_readings |  | JOB | 2026-10-05T22:33:01.658Z | 2 |
| serverless_stable_am1uc2_catalog.pdm_ml.history_readings | serverless_stable_am1uc2_catalog.pdm_ml.training_features | JOB | 2026-10-05T22:39:06.086Z | 2 |
| serverless_stable_am1uc2_catalog.pdm_ml.training_features |  | JOB | 2026-10-05T22:39:17.745Z | 8 |
| serverless_stable_am1uc2_catalog.pdm_ops.lb_sim_commands_history |  | JOB | 2026-10-06T17:22:49.614Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_ops.lb_sim_commands_history |  |  | 2026-10-06T17:14:13.263Z | 1 |
| serverless_stable_am1uc2_catalog.pdm_ops.lb_work_orders_history |  | JOB | 2026-10-06T18:03:03.077Z | 1 |
... 24 more rows
