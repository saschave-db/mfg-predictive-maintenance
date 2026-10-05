# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Live evidence: latency, data quality, and a fault traced end to end
# MAGIC Run while the simulator and the continuous pipeline are live. Every number below is queried from the live tables.
# MAGIC 1. Throughput and per-hop latency (sensor -> Zerobus/bronze -> silver -> features -> risk score)
# MAGIC 2. Data-quality expectations from the SDP event log
# MAGIC 3. A fault injected from the app (Lakebase `sim_commands`), traced through the pipeline to a HIGH risk alert

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Throughput and latency over the last 10 minutes

# COMMAND ----------

display(spark.sql("""
SELECT count(*) AS bronze_rows_last_10min, count(DISTINCT station_id) AS stations,
       round(count(*) / 600.0, 1) AS rows_per_second, max(ts) AS newest_reading
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES"""))

# COMMAND ----------

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

# COMMAND ----------

display(spark.sql("""
SELECT risk_band, count(*) AS stations, round(avg(failure_probability) * 100, 1) AS avg_risk_pct,
       max(window_end) AS latest_window
FROM pdm_core.station_health_current GROUP BY ALL ORDER BY stations DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Data-quality expectations (SDP event log)

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Fault injected from the app, traced to an alert
# MAGIC The command row in Lakebase `pdm_ops.sim_commands` (replicated to UC by Lakehouse Sync) shows when the app requested
# MAGIC the fault and when the gateway simulator applied it. The risk scores show how the model reacted.

# COMMAND ----------

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
