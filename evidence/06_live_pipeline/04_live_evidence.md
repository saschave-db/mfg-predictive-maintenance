# Executed notebook: 04_live_evidence

Exported from Databricks job run `260989640533510` (task `evidence`, task run `804427246380522`).

Result: **SUCCESS** · start 2026-10-06T17:22:07.970000+00:00 · end 2026-10-06T17:22:57.589000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/565657892038932/run/260989640533510


# 04 · Live evidence: latency, data quality, and a fault traced end to end
Run while the simulator and the continuous pipeline are live. Every number below is queried from the live tables.
1. Throughput and per-hop latency (sensor -> Zerobus/bronze -> silver -> features -> risk score)
2. Data-quality expectations from the SDP event log
3. A fault injected from the app (Lakebase `sim_commands`), traced through the pipeline to a HIGH risk alert

```python
dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("pipeline_id", "")
dbutils.widgets.text("station_id", "")
dbutils.widgets.text("injected_at_utc", "")
CATALOG = dbutils.widgets.get("catalog")
PIPELINE_ID = dbutils.widgets.get("pipeline_id")
STATION = dbutils.widgets.get("station_id")
INJECTED_AT = dbutils.widgets.get("injected_at_utc")
spark.sql(f"USE CATALOG {CATALOG}")
print("now (UTC):", spark.sql("SELECT current_timestamp()").first()[0])
```

Output:

```text
now (UTC): 2026-10-06 17:22:21.732920
```

## 1 · Throughput and latency over the last 10 minutes

```python
display(spark.sql("""
SELECT count(*) AS bronze_rows_last_10min, count(DISTINCT station_id) AS stations,
       round(count(*) / 600.0, 1) AS rows_per_second, max(ts) AS newest_reading
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES"""))
```

Output:

| bronze_rows_last_10min | stations | rows_per_second | newest_reading |
|---|---|---|---|
| 57312 | 96 | 95.5 | 2026-10-06T17:22:23.000Z |

```python
display(spark.sql("""
WITH s AS (
  SELECT (unix_millis(silver_at) - unix_millis(ts)) / 1000.0 AS sensor_to_silver_s
  FROM pdm_core.sensor_readings_clean WHERE ts > current_timestamp() - INTERVAL 10 MINUTES
), r AS (
  SELECT (unix_millis(features_at) - unix_millis(last_reading_ts)) / 1000.0 AS sensor_to_features_s,
         (unix_millis(scored_at) - unix_millis(last_reading_ts)) / 1000.0 AS sensor_to_score_s,
         (unix_millis(scored_at) - unix_millis(features_at)) / 1000.0 AS features_to_score_s
  FROM pdm_core.station_risk_scores WHERE window_end > current_timestamp() - INTERVAL 10 MINUTES
)
SELECT 'sensor -> silver (Zerobus + bronze + SDP silver)' AS hop,
       round(percentile(sensor_to_silver_s, 0.5), 1) AS p50_s, round(percentile(sensor_to_silver_s, 0.95), 1) AS p95_s, count(*) AS n FROM s
UNION ALL SELECT 'sensor -> window features (incl. 10 s watermark)', round(percentile(sensor_to_features_s, 0.5), 1),
       round(percentile(sensor_to_features_s, 0.95), 1), count(*) FROM r
UNION ALL SELECT 'features -> risk score (in-stream model)', round(percentile(features_to_score_s, 0.5), 1),
       round(percentile(features_to_score_s, 0.95), 1), count(*) FROM r
UNION ALL SELECT 'sensor -> risk score (end to end in Delta)', round(percentile(sensor_to_score_s, 0.5), 1),
       round(percentile(sensor_to_score_s, 0.95), 1), count(*) FROM r"""))
```

Output:

| hop | p50_s | p95_s | n |
|---|---|---|---|
| sensor -> silver (Zerobus + bronze + SDP silver) | 3.9 | 7.7 | 56832 |
| sensor -> window features (incl. 10 s watermark) | 38.0 | 43.2 | 5376 |
| features -> risk score (in-stream model) | 0.0 | 0.0 | 5376 |
| sensor -> risk score (end to end in Delta) | 38.0 | 43.2 | 5376 |

```python
display(spark.sql("""
SELECT risk_band, count(*) AS stations, round(avg(failure_probability) * 100, 1) AS avg_risk_pct,
       max(window_end) AS latest_window
FROM pdm_core.station_health_current GROUP BY ALL ORDER BY stations DESC"""))
```

Output:

| risk_band | stations | avg_risk_pct | latest_window |
|---|---|---|---|
| NORMAL | 89 | 3.2 | 2026-10-06T17:21:50.000Z |
| HIGH | 4 | 99.9 | 2026-10-06T17:21:50.000Z |
| ELEVATED | 3 | 51.8 | 2026-10-06T17:21:50.000Z |

## 2 · Data-quality expectations (SDP event log)

```python
if PIPELINE_ID:
    display(spark.sql(f"""
    SELECT flow_name, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed
    FROM (
      SELECT origin.flow_name AS flow_name,
             explode(from_json(details:flow_progress.data_quality.expectations,
                     'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x
      FROM event_log('{PIPELINE_ID}')
      WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL
    )
    GROUP BY ALL ORDER BY expectation"""))
    display(spark.sql(f"""
    SELECT origin.flow_name AS flow, count(*) AS micro_batches_last_10min,
           sum(details:flow_progress.metrics.num_output_rows::bigint) AS output_rows
    FROM event_log('{PIPELINE_ID}')
    WHERE event_type = 'flow_progress' AND timestamp > current_timestamp() - INTERVAL 10 MINUTES
      AND details:flow_progress.metrics.num_output_rows IS NOT NULL
    GROUP BY ALL ORDER BY flow"""))
```

Output:

| flow_name | expectation | passed | failed |
|---|---|---|---|
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | complete_window | 25248 | 7392 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | current_in_range | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | not_from_future | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | pressure_in_range | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | temperature_in_range | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | valid_station | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | valid_ts | 429984 | 0 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | vibration_in_range | 429984 | 0 |

Output:

| flow | micro_batches_last_10min | output_rows |
|---|---|---|
| serverless_stable_am1uc2_catalog.pdm_core.maintenance_events | 10 | 24610 |
| serverless_stable_am1uc2_catalog.pdm_core.sensor_readings_clean | 149 | 57600 |
| serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores | 85 | 5760 |

## 3 · Fault injected from the app, traced to an alert
The command row in Lakebase `pdm_ops.sim_commands` (replicated to UC by Lakehouse Sync) shows when the app requested
the fault and when the gateway simulator applied it. The risk scores show how the model reacted.

```python
if STATION:
    display(spark.sql(f"""
    SELECT command_id, command, station_id, failure_mode, requested_by, status, requested_at, applied_at, _pg_change_type
    FROM pdm_ops.lb_sim_commands_history WHERE station_id = '{STATION}' ORDER BY _pg_lsn"""))
    display(spark.sql(f"""
    SELECT window_end, round(failure_probability * 100, 1) AS risk_pct, risk_band, top_signal, top_signal_deviation_pct,
           round(avg_vibration_rms, 2) AS vibration, round(avg_bearing_temp_c, 1) AS temp_c,
           round(avg_hydraulic_pressure_bar, 1) AS pressure, round(avg_motor_current_a, 1) AS current_a
    FROM pdm_core.station_risk_scores
    WHERE station_id = '{STATION}' AND window_end >= timestamp'{INJECTED_AT}' - INTERVAL 1 MINUTE
      AND second(window_end) % 30 = 0
    ORDER BY window_end LIMIT 40"""))
    display(spark.sql(f"""
    WITH s AS (SELECT * FROM pdm_core.station_risk_scores WHERE station_id = '{STATION}' AND window_end >= timestamp'{INJECTED_AT}')
    SELECT timestamp'{INJECTED_AT}' AS injected_at,
           min(window_end) FILTER (WHERE risk_band IN ('ELEVATED', 'HIGH')) AS first_elevated,
           min(window_end) FILTER (WHERE risk_band = 'HIGH') AS first_high,
           min(window_end) FILTER (WHERE risk_band = 'DOWN') AS station_down,
           round((unix_seconds(min(window_end) FILTER (WHERE risk_band = 'DOWN'))
                - unix_seconds(min(window_end) FILTER (WHERE risk_band = 'HIGH'))), 0) AS warning_before_failure_s
    FROM s"""))
```

Output:

| command_id | command | station_id | failure_mode | requested_by | status | requested_at | applied_at | _pg_change_type |
|---|---|---|---|---|---|---|---|---|
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | pending | 2026-10-06T17:12:38.582Z |  | insert |
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | applied | 2026-10-06T17:12:38.582Z | 2026-10-06T17:12:39.001Z | update_postimage |
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | pending | 2026-10-06T17:12:38.582Z |  | update_preimage |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | pending | 2026-10-06T17:17:43.295Z |  | insert |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | pending | 2026-10-06T17:17:43.295Z |  | update_preimage |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | applied | 2026-10-06T17:17:43.295Z | 2026-10-06T17:17:45.001Z | update_postimage |

Output:

| window_end | risk_pct | risk_band | top_signal | top_signal_deviation_pct | vibration | temp_c | pressure | current_a |
|---|---|---|---|---|---|---|---|---|
| 2026-10-06T17:12:00.000Z | 1.1 | NORMAL | motor_current_a | 8.5 | 0.78 | 62.2 | 6.0 | 130.2 |
| 2026-10-06T17:12:30.000Z | 1.1 | NORMAL | motor_current_a | 8.4 | 0.78 | 62.1 | 6.0 | 130.1 |
| 2026-10-06T17:13:00.000Z | 0.9 | NORMAL | cycle_time_s | 8.3 | 0.79 | 62.2 | 6.0 | 129.9 |
| 2026-10-06T17:13:30.000Z | 0.7 | NORMAL | motor_current_a | 7.9 | 0.79 | 62.1 | 6.0 | 129.5 |
| 2026-10-06T17:14:00.000Z | 0.8 | NORMAL | motor_current_a | 7.7 | 0.79 | 62.2 | 6.0 | 129.3 |
| 2026-10-06T17:14:30.000Z | 1.8 | NORMAL | motor_current_a | 7.5 | 0.8 | 62.6 | 6.0 | 128.9 |
| 2026-10-06T17:15:00.000Z | 4.6 | NORMAL | motor_current_a | 7.7 | 0.8 | 63.0 | 6.0 | 129.3 |
| 2026-10-06T17:15:30.000Z | 67.7 | ELEVATED | motor_current_a | 8.5 | 0.8 | 63.9 | 6.0 | 130.2 |
| 2026-10-06T17:16:00.000Z | 86.7 | HIGH | motor_current_a | 9.2 | 0.82 | 64.9 | 6.0 | 131.1 |
| 2026-10-06T17:16:30.000Z | 98.4 | HIGH | motor_current_a | 10.4 | 0.83 | 66.2 | 6.0 | 132.5 |
| 2026-10-06T17:17:00.000Z | 99.5 | HIGH | bearing_temp_c | 13.1 | 0.85 | 67.8 | 6.0 | 133.7 |
| 2026-10-06T17:17:30.000Z | 99.8 | HIGH | bearing_temp_c | 16.3 | 0.88 | 69.8 | 6.0 | 134.9 |
| 2026-10-06T17:18:00.000Z | 95.6 | HIGH | bearing_temp_c | 16.9 | 0.87 | 70.1 | 6.0 | 134.7 |
| 2026-10-06T17:18:30.000Z | 97.5 | HIGH | bearing_temp_c | 14.1 | 0.86 | 68.4 | 6.0 | 131.2 |
| 2026-10-06T17:19:00.000Z | 93.6 | HIGH | bearing_temp_c | 10.4 | 0.83 | 66.3 | 6.0 | 127.2 |
| 2026-10-06T17:19:30.000Z | 96.3 | HIGH | bearing_temp_c | 5.6 | 0.8 | 63.4 | 6.0 | 122.8 |
| 2026-10-06T17:20:00.000Z | 1.0 | NORMAL | spindle_rpm | 2.8 | 0.81 | 61.6 | 6.0 | 119.8 |
| 2026-10-06T17:20:30.000Z | 1.2 | NORMAL | spindle_rpm | 2.8 | 0.81 | 61.6 | 6.0 | 119.2 |
| 2026-10-06T17:21:00.000Z | 1.1 | NORMAL | spindle_rpm | 2.8 | 0.8 | 61.4 | 6.0 | 118.5 |
| 2026-10-06T17:21:30.000Z | 0.6 | NORMAL | spindle_rpm | 2.7 | 0.8 | 61.3 | 6.0 | 118.0 |
| 2026-10-06T17:22:00.000Z | 0.6 | NORMAL | spindle_rpm | 2.6 | 0.78 | 61.3 | 6.0 | 117.1 |

Output:

| injected_at | first_elevated | first_high | station_down | warning_before_failure_s |
|---|---|---|---|---|
| 2026-10-06T17:12:38.000Z | 2026-10-06T17:15:20.000Z | 2026-10-06T17:15:40.000Z |  |  |
