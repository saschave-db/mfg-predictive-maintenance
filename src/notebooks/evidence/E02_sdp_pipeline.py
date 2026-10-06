# Databricks notebook source
# MAGIC %md
# MAGIC # E02 · ETL with Lakeflow Spark Declarative Pipelines (continuous)
# MAGIC
# MAGIC **What was built.** Pipeline `pdm_live_pipeline` (serverless, continuous) with four datasets:
# MAGIC
# MAGIC | Dataset | Type | Logic |
# MAGIC |---|---|---|
# MAGIC | `sensor_readings_clean` | streaming table | Reads Zerobus bronze, watermark 30 s, `dropDuplicatesWithinWatermark(event_id)`, 6 drop expectations + 1 warn expectation, joins station nominals |
# MAGIC | `station_risk_scores` | streaming table | 2-minute sliding windows every 10 s (shared `pdm.features`), drops incomplete windows (`expect_or_drop n_readings >= 110`), scores in-stream with UC model `@champion` |
# MAGIC | `station_health_current` | streaming table (AUTO CDC SCD1) | Latest risk row per station |
# MAGIC | `maintenance_events` | materialized view | Maintenance log joined with station context |
# MAGIC
# MAGIC **What this notebook proves.** The deployed spec, the update history, that every flow is running, data-quality
# MAGIC results from the event log, row counts and freshness per table, and column-level lineage captured by Unity Catalog.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Deployed pipeline specification

# COMMAND ----------

p = w.pipelines.get(PIPELINE_ID)
show({"name": p.name, "state": p.state.value, "continuous": p.spec.continuous, "serverless": p.spec.serverless,
      "photon": p.spec.photon, "catalog": p.spec.catalog, "schema": p.spec.schema, "channel": p.spec.channel,
      "libraries": [l.file.path.split("/files/")[-1] for l in p.spec.libraries],
      "environment": p.spec.environment.as_dict() if p.spec.environment else None})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Update history and current flow states (event log)

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Data-quality expectations (cumulative, current update)

# COMMAND ----------

display(spark.sql(f"""
SELECT split(flow_name, '\\\\.')[2] AS dataset, x.name AS expectation, sum(x.passed_records) AS passed, sum(x.failed_records) AS failed_or_dropped
FROM (SELECT origin.flow_name AS flow_name, explode(from_json(details:flow_progress.data_quality.expectations,
        'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS x
      FROM event_log('{PIPELINE_ID}') WHERE event_type = 'flow_progress')
GROUP BY ALL ORDER BY dataset, expectation"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Row counts and freshness per table

# COMMAND ----------

display(spark.sql("""
SELECT 'pdm_raw.sensor_readings (bronze, Zerobus)' AS table_name, count(*) AS rows, max(ts) AS newest, timestampdiff(SECOND, max(ts), current_timestamp()) AS seconds_behind FROM pdm_raw.sensor_readings
UNION ALL SELECT 'pdm_core.sensor_readings_clean (silver)', count(*), max(ts), timestampdiff(SECOND, max(ts), current_timestamp()) FROM pdm_core.sensor_readings_clean
UNION ALL SELECT 'pdm_core.station_risk_scores (gold)', count(*), max(window_end), timestampdiff(SECOND, max(window_end), current_timestamp()) FROM pdm_core.station_risk_scores
UNION ALL SELECT 'pdm_core.station_health_current (gold)', count(*), max(window_end), timestampdiff(SECOND, max(window_end), current_timestamp()) FROM pdm_core.station_health_current
UNION ALL SELECT 'pdm_core.maintenance_events (MV)', count(*), max(event_ts), NULL FROM pdm_core.maintenance_events"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Per-hop latency (last 10 minutes)

# COMMAND ----------

display(spark.sql("""
SELECT 'sensor -> silver' AS hop, round(percentile((unix_millis(silver_at) - unix_millis(ts)) / 1000, 0.5), 1) AS p50_s,
       round(percentile((unix_millis(silver_at) - unix_millis(ts)) / 1000, 0.95), 1) AS p95_s
FROM pdm_core.sensor_readings_clean WHERE ts > current_timestamp() - INTERVAL 10 MINUTES
UNION ALL
SELECT 'sensor -> risk score', round(percentile((unix_millis(scored_at) - unix_millis(last_reading_ts)) / 1000, 0.5), 1),
       round(percentile((unix_millis(scored_at) - unix_millis(last_reading_ts)) / 1000, 0.95), 1)
FROM pdm_core.station_risk_scores WHERE window_end > current_timestamp() - INTERVAL 10 MINUTES"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · Sample output rows

# COMMAND ----------

display(spark.sql("""SELECT station_id, window_start, window_end, n_readings, failure_probability, risk_band, top_signal,
                     top_signal_deviation_pct, round(avg_vibration_rms, 2) AS vib, round(avg_bearing_temp_c, 1) AS temp, model_uri
                     FROM pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 10"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7 · Lineage captured by Unity Catalog
# MAGIC `system.access.table_lineage` records the table-to-table flow from the Zerobus landing table through the pipeline
# MAGIC to the Lakebase sync and metric views. (System-table lineage can lag by some minutes.)

# COMMAND ----------

display(spark.sql(f"""
SELECT source_table_full_name, target_table_full_name, entity_type, max(event_time) AS last_seen, count(*) AS events
FROM system.access.table_lineage
WHERE (source_table_catalog = '{CATALOG}' AND source_table_schema LIKE 'pdm_%')
   OR (target_table_catalog = '{CATALOG}' AND target_table_schema LIKE 'pdm_%')
GROUP BY ALL ORDER BY source_table_full_name, target_table_full_name"""))
