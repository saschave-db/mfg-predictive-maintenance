# Databricks notebook source
# MAGIC %md
# MAGIC # E01 · Data generation and Lakeflow Connect Zerobus ingestion
# MAGIC
# MAGIC **What was built.** A physics-lite simulator (`src/pdm/physics.py`) models 96 stations (3 plants x 4 lines x 8 stations).
# MAGIC Each station has a hidden health that degrades in episodes with failure-mode signatures (bearing wear, overheating,
# MAGIC seal leak). The live producer (`src/simulator/zerobus_producer.py`) runs as a serverless job and pushes one JSON record per
# MAGIC station per second through **three Zerobus streams**, one per plant gateway, into the managed Delta table
# MAGIC `pdm_raw.sensor_readings`. It authenticates as the service principal `pdm-zerobus-producer` (OAuth M2M, secret in a
# MAGIC secret scope).
# MAGIC
# MAGIC **What this notebook proves.**
# MAGIC 1. The producer job is running on serverless compute.
# MAGIC 2. The service principal has only table-level `MODIFY`/`SELECT` (least privilege).
# MAGIC 3. The Delta commit history shows the data is committed **by the Zerobus service** (`engineInfo = 'Zerobus'`), in small
# MAGIC    commits every few seconds. Zerobus does not record a `userName` on these commits; the identity is the service principal,
# MAGIC    the only principal besides the table owner with `MODIFY` (section 2), whose OAuth secret the producer uses.
# MAGIC 4. Rows arrive continuously at ~96 rows/s from all three gateways, with per-second freshness.
# MAGIC 5. Duplicates (Zerobus is at-least-once) are measured and removed downstream.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import datetime
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · The producer job and its run

# COMMAND ----------

job = w.jobs.get(next(j for j in w.jobs.list(name="pdm_simulator_zerobus")).job_id)  # list() omits tasks
env = job.settings.environments[0].spec
print("job:", job.settings.name, "| job_id:", job.job_id)
print("compute: serverless environment", env.environment_version, "| dependencies:", env.dependencies)
print("task parameters:", job.settings.tasks[0].spark_python_task.parameters)
for r in w.jobs.list_runs(job_id=job.job_id, limit=5):
    print(f"run {r.run_id}: {r.state.life_cycle_state.value} {r.state.result_state.value if r.state.result_state else ''} "
          f"started {datetime.datetime.utcfromtimestamp(r.start_time / 1000).isoformat() if r.start_time else ''}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Least-privilege grants for the Zerobus service principal

# COMMAND ----------

print("service principal:", w.service_principals.list(filter=f"applicationId eq {ZEROBUS_SP}").__next__().display_name, ZEROBUS_SP)
display(spark.sql(f"SHOW GRANTS `{ZEROBUS_SP}` ON TABLE pdm_raw.sensor_readings"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Delta commit history: who wrote the data
# MAGIC `engineInfo` identifies the writer engine. All data commits come from Zerobus; the only other commits are the table
# MAGIC creation and automatic maintenance (OPTIMIZE).

# COMMAND ----------

display(spark.sql("""
SELECT version, timestamp, coalesce(nullif(userName, ''), '(not recorded)') AS userName, operation, engineInfo
FROM (DESCRIBE HISTORY pdm_raw.sensor_readings) ORDER BY version DESC LIMIT 10"""))
display(spark.sql("""
SELECT engineInfo, operation, count(*) AS commits, min(timestamp) AS first_commit, max(timestamp) AS last_commit
FROM (DESCRIBE HISTORY pdm_raw.sensor_readings) GROUP BY ALL ORDER BY commits DESC"""))
display(spark.sql("""
WITH c AS (SELECT timestamp, lag(timestamp) OVER (ORDER BY version) AS prev
           FROM (DESCRIBE HISTORY pdm_raw.sensor_readings) WHERE engineInfo = 'Zerobus')
SELECT count(*) AS zerobus_commits_last_10min, round(avg(unix_seconds(timestamp) - unix_seconds(prev)), 1) AS avg_seconds_between_commits
FROM c WHERE timestamp > current_timestamp() - INTERVAL 10 MINUTES"""))

# COMMAND ----------

# MAGIC ## 4 · Throughput and freshness per gateway (last 10 minutes)

# COMMAND ----------

display(spark.sql("""
SELECT gateway_id, count(*) AS rows, count(DISTINCT station_id) AS stations, round(count(*) / 600.0, 1) AS rows_per_s,
       max(ts) AS newest_reading, timestampdiff(SECOND, max(ts), current_timestamp()) AS seconds_behind_now
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY gateway_id"""))
display(spark.sql("""
SELECT date_trunc('MINUTE', ts) AS minute, count(*) AS rows, count(DISTINCT station_id) AS stations
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY minute"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Sample records and duplicate rate
# MAGIC `event_id` = station + second. Duplicates would come from Zerobus retries (at-least-once); silver removes them.

# COMMAND ----------

display(spark.sql("SELECT * FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 1 MINUTE ORDER BY ts DESC, station_id LIMIT 8"))
display(spark.sql("""
SELECT (SELECT count(*) FROM pdm_raw.sensor_readings) AS bronze_rows,
       (SELECT count(DISTINCT event_id) FROM pdm_raw.sensor_readings) AS distinct_event_ids,
       (SELECT count(*) FROM pdm_core.sensor_readings_clean) AS silver_rows"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · The simulated degradation is visible in the raw data
# MAGIC Stations in a degradation episode drift away from their nominal operating point. This lists stations whose
# MAGIC last-minute average deviates most from nominal, by sensor.

# COMMAND ----------

display(spark.sql("""
WITH last AS (
  SELECT r.station_id, s.station_type,
         avg(r.vibration_rms / s.nom_vibration_rms) AS vib_ratio, avg(r.bearing_temp_c / s.nom_bearing_temp_c) AS temp_ratio,
         avg(r.hydraulic_pressure_bar / s.nom_hydraulic_pressure_bar) AS pressure_ratio, avg(r.spindle_rpm) AS rpm
  FROM pdm_raw.sensor_readings r JOIN pdm_raw.station_master s USING (station_id)
  WHERE r.ts > current_timestamp() - INTERVAL 1 MINUTE GROUP BY ALL)
SELECT station_id, station_type, round(vib_ratio, 2) AS vibration_x_nominal, round(temp_ratio, 2) AS temp_x_nominal,
       round(pressure_ratio, 2) AS pressure_x_nominal, round(rpm) AS rpm
FROM last ORDER BY greatest(abs(vib_ratio - 1), abs(temp_ratio - 1), abs(pressure_ratio - 1)) DESC LIMIT 10"""))
