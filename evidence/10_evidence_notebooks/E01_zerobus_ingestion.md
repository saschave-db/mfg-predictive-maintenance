# Executed notebook: E01_zerobus_ingestion

Exported from Databricks job run `980301348000608` (task `E01_zerobus_ingestion`, task run `96008841838528`).

Result: **SUCCESS** · start 2026-10-06T18:06:35.144000+00:00 · end 2026-10-06T18:08:06.766000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


# E01 · Data generation and Lakeflow Connect Zerobus ingestion

**What was built.** A physics-lite simulator (`src/pdm/physics.py`) models 96 stations (3 plants x 4 lines x 8 stations).
Each station has a hidden health that degrades in episodes with failure-mode signatures (bearing wear, overheating,
seal leak). The live producer (`src/simulator/zerobus_producer.py`) runs as a serverless job and pushes one JSON record per
station per second through **three Zerobus streams**, one per plant gateway, into the managed Delta table
`pdm_raw.sensor_readings`. It authenticates as the service principal `pdm-zerobus-producer` (OAuth M2M, secret in a
secret scope).

**What this notebook proves.**
1. The producer job is running on serverless compute.
2. The service principal has only table-level `MODIFY`/`SELECT` (least privilege).
3. The Delta commit history shows the data is committed **by the Zerobus service** (`engineInfo = 'Zerobus'`), in small
   commits every few seconds. Zerobus does not record a `userName` on these commits; the identity is the service principal,
   the only principal besides the table owner with `MODIFY` (section 2), whose OAuth secret the producer uses.
4. Rows arrive continuously at ~96 rows/s from all three gateways, with per-second freshness.
5. Duplicates (Zerobus is at-least-once) are measured and removed downstream.

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
import datetime
spark.sql(f"USE CATALOG {CATALOG}")
```

Output:

```text
{"text/plain": "DataFrame[]"}
```

## 1 · The producer job and its run

```python
job = w.jobs.get(next(j for j in w.jobs.list(name="pdm_simulator_zerobus")).job_id)  # list() omits tasks
env = job.settings.environments[0].spec
print("job:", job.settings.name, "| job_id:", job.job_id)
print("compute: serverless environment", env.environment_version, "| dependencies:", env.dependencies)
print("task parameters:", job.settings.tasks[0].spark_python_task.parameters)
for r in w.jobs.list_runs(job_id=job.job_id, limit=5):
    print(f"run {r.run_id}: {r.state.life_cycle_state.value} {r.state.result_state.value if r.state.result_state else ''} "
          f"started {datetime.datetime.utcfromtimestamp(r.start_time / 1000).isoformat() if r.start_time else ''}")
```

Output:

```text
job: pdm_simulator_zerobus | job_id: 16077621483238
compute: serverless environment 4 | dependencies: ['databricks-zerobus-ingest-sdk>=1.0.0', 'databricks-sdk>=0.81.0', 'pg8000>=1.31']
task parameters: ['--src-path=/Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src', '--catalog=serverless_stable_am1uc2_catalog', '--endpoint=7474651880045550.zerobus.us-east-2.cloud.databricks.com', '--duration-min={{job.parameters.duration_min}}', '--lakebase-endpoint=projects/pdm-demo/branches/production/endpoints/primary', '--lakebase-host=ep-autumn-paper-d8fiis3p.database.us-east-2.cloud.databricks.com', '--extra={{job.parameters.extra_args}}']
run 433290942380103: RUNNING  started 2026-10-06T16:54:20.522000
run 320983066504714: TERMINATED CANCELED started 2026-10-05T22:27:17.055000
```

Output:

```text
/home/spark-3c2cbc6d-c4e7-474c-8926-b4/.ipykernel/67/command-6364727878986308-2057826776:8: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
  f"started {datetime.datetime.utcfromtimestamp(r.start_time / 1000).isoformat() if r.start_time else ''}")
```

## 2 · Least-privilege grants for the Zerobus service principal

```python
print("service principal:", w.service_principals.list(filter=f"applicationId eq {ZEROBUS_SP}").__next__().display_name, ZEROBUS_SP)
display(spark.sql(f"SHOW GRANTS `{ZEROBUS_SP}` ON TABLE pdm_raw.sensor_readings"))
```

Output:

```text
service principal: pdm-zerobus-producer 240a5501-f956-4282-a2a7-ccc7614683a7
```

Output:

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 240a5501-f956-4282-a2a7-ccc7614683a7 | MODIFY | TABLE | serverless_stable_am1uc2_catalog.pdm_raw.sensor_readings |
| 240a5501-f956-4282-a2a7-ccc7614683a7 | SELECT | TABLE | serverless_stable_am1uc2_catalog.pdm_raw.sensor_readings |

## 3 · Delta commit history: who wrote the data
`engineInfo` identifies the writer engine. All data commits come from Zerobus; the only other commits are the table
creation and automatic maintenance (OPTIMIZE).

```python
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
```

Output:

| version | timestamp | userName | operation | engineInfo |
|---|---|---|---|---|
| 1157 | 2026-10-06T18:07:10.000Z | (not recorded) | WRITE | Zerobus |
| 1156 | 2026-10-06T18:07:05.000Z | (not recorded) | WRITE | Zerobus |
| 1155 | 2026-10-06T18:07:00.000Z | (not recorded) | WRITE | Zerobus |
| 1154 | 2026-10-06T18:06:55.000Z | (not recorded) | WRITE | Zerobus |
| 1153 | 2026-10-06T18:06:50.000Z | (not recorded) | WRITE | Zerobus |
| 1152 | 2026-10-06T18:06:45.000Z | (not recorded) | WRITE | Zerobus |
| 1151 | 2026-10-06T18:06:40.000Z | (not recorded) | WRITE | Zerobus |
| 1150 | 2026-10-06T18:06:35.000Z | (not recorded) | WRITE | Zerobus |
| 1149 | 2026-10-06T18:06:30.000Z | (not recorded) | WRITE | Zerobus |
| 1148 | 2026-10-06T18:06:25.000Z | (not recorded) | WRITE | Zerobus |

Output:

| engineInfo | operation | commits | first_commit | last_commit |
|---|---|---|---|---|
| Zerobus | WRITE | 1157 | 2026-10-05T22:07:30.000Z | 2026-10-06T18:07:20.000Z |
| Databricks-Runtime/19.8.x-aarch64-photon-scala2.13 | OPTIMIZE | 1 | 2026-10-05T22:53:49.000Z | 2026-10-05T22:53:49.000Z |
| Databricks-Runtime/19.9.x-aarch64-photon-scala2.13 | OPTIMIZE | 1 | 2026-10-06T17:15:44.000Z | 2026-10-06T17:15:44.000Z |
| Databricks-Runtime/19.9.x-aarch64-photon-scala2.13 | CREATE TABLE | 1 | 2026-10-05T21:57:47.000Z | 2026-10-05T21:57:47.000Z |

Output:

| zerobus_commits_last_10min | avg_seconds_between_commits |
|---|---|
| 120 | 5.0 |

```python
## 4 · Throughput and freshness per gateway (last 10 minutes)
```

```python
display(spark.sql("""
SELECT gateway_id, count(*) AS rows, count(DISTINCT station_id) AS stations, round(count(*) / 600.0, 1) AS rows_per_s,
       max(ts) AS newest_reading, timestampdiff(SECOND, max(ts), current_timestamp()) AS seconds_behind_now
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY gateway_id"""))
display(spark.sql("""
SELECT date_trunc('MINUTE', ts) AS minute, count(*) AS rows, count(DISTINCT station_id) AS stations
FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY minute"""))
```

Output:

| gateway_id | rows | stations | rows_per_s | newest_reading | seconds_behind_now |
|---|---|---|---|---|---|
| gw-plt-e | 19040 | 32 | 31.7 | 2026-10-06T18:07:39.000Z | 5 |
| gw-plt-n | 19040 | 32 | 31.7 | 2026-10-06T18:07:39.000Z | 5 |
| gw-plt-s | 19040 | 32 | 31.7 | 2026-10-06T18:07:39.000Z | 5 |

Output:

| minute | rows | stations |
|---|---|---|
| 2026-10-06T17:57:00.000Z | 768 | 96 |
| 2026-10-06T17:58:00.000Z | 5760 | 96 |
| 2026-10-06T17:59:00.000Z | 5760 | 96 |
| 2026-10-06T18:00:00.000Z | 5760 | 96 |
| 2026-10-06T18:01:00.000Z | 5760 | 96 |
| 2026-10-06T18:02:00.000Z | 5760 | 96 |
| 2026-10-06T18:03:00.000Z | 5760 | 96 |
| 2026-10-06T18:04:00.000Z | 5760 | 96 |
| 2026-10-06T18:05:00.000Z | 5760 | 96 |
| 2026-10-06T18:06:00.000Z | 5760 | 96 |
| 2026-10-06T18:07:00.000Z | 4800 | 96 |

## 5 · Sample records and duplicate rate
`event_id` = station + second. Duplicates would come from Zerobus retries (at-least-once); silver removes them.

```python
display(spark.sql("SELECT * FROM pdm_raw.sensor_readings WHERE ts > current_timestamp() - INTERVAL 1 MINUTE ORDER BY ts DESC, station_id LIMIT 8"))
display(spark.sql("""
SELECT (SELECT count(*) FROM pdm_raw.sensor_readings) AS bronze_rows,
       (SELECT count(DISTINCT event_id) FROM pdm_raw.sensor_readings) AS distinct_event_ids,
       (SELECT count(*) FROM pdm_core.sensor_readings_clean) AS silver_rows"""))
```

Output:

| event_id | gateway_id | plant_id | line_id | station_id | ts | seq | vibration_rms | bearing_temp_c | motor_current_a | spindle_rpm | hydraulic_pressure_bar | acoustic_db | cycle_time_s | firmware |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PLT-E-A01-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A01 | 2026-10-06T18:07:49.000Z | 1791310069 | 1.894 | 45.893 | 32.668 | 1245.745 | 185.074 | 84.326 | 10.744 | gw-fw-3.2.1 |
| PLT-E-A02-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A02 | 2026-10-06T18:07:49.000Z | 1791310069 | 1.518 | 54.105 | 18.741 | 9132.268 | 61.372 | 73.418 | 47.82 | gw-fw-3.2.1 |
| PLT-E-A03-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A03 | 2026-10-06T18:07:49.000Z | 1791310069 | 0.78 | 63.754 | 121.557 | 307.416 | 5.972 | 69.772 | 19.035 | gw-fw-3.2.1 |
| PLT-E-A04-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A04 | 2026-10-06T18:07:49.000Z | 1791310069 | 0.896 | 41.078 | 11.207 | 3130.321 | 5.978 | 67.691 | 15.096 | gw-fw-3.2.1 |
| PLT-E-A05-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A05 | 2026-10-06T18:07:49.000Z | 1791310069 | 1.287 | 40.374 | 7.498 | 1390.915 | 5.843 | 66.389 | 5.421 | gw-fw-3.2.1 |
| PLT-E-A06-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A06 | 2026-10-06T18:07:49.000Z | 1791310069 | 1.447 | 48.626 | 15.677 | 9205.837 | 60.364 | 67.882 | 45.055 | gw-fw-3.2.1 |
| PLT-E-A07-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A07 | 2026-10-06T18:07:49.000Z | 1791310069 | 0.744 | 60.134 | 110.71 | 299.755 | 6.408 | 69.42 | 18.291 | gw-fw-3.2.1 |
| PLT-E-A08-1791310069 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A08 | 2026-10-06T18:07:49.000Z | 1791310069 | 1.803 | 45.251 | 28.841 | 1146.993 | 169.307 | 74.306 | 12.915 | gw-fw-3.2.1 |

Output:

| bronze_rows | distinct_event_ids | silver_rows |
|---|---|---|
| 558528 | 558528 | 558048 |

## 6 · The simulated degradation is visible in the raw data
Stations in a degradation episode drift away from their nominal operating point. This lists stations whose
last-minute average deviates most from nominal, by sensor.

```python
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
```

Output:

| station_id | station_type | vibration_x_nominal | temp_x_nominal | pressure_x_nominal | rpm |
|---|---|---|---|---|---|
| PLT-N-C03 | welder | 0.21 | 0.83 | 1.0 | 47.0 |
| PLT-S-B02 | cnc_mill | 0.65 | 0.96 | 0.97 | 6175.0 |
| PLT-S-B07 | welder | 1.23 | 1.24 | 1.05 | 288.0 |
| PLT-S-B06 | cnc_mill | 1.2 | 1.0 | 1.09 | 8695.0 |
| PLT-S-A01 | press | 1.19 | 0.98 | 1.02 | 1174.0 |
| PLT-S-C02 | cnc_mill | 1.17 | 1.17 | 1.01 | 8823.0 |
| PLT-N-D05 | conveyor | 1.14 | 1.06 | 1.06 | 1410.0 |
| PLT-S-B04 | robot_arm | 1.13 | 0.93 | 0.96 | 3042.0 |
| PLT-N-A06 | cnc_mill | 1.12 | 0.99 | 1.02 | 8813.0 |
| PLT-E-D05 | conveyor | 0.95 | 0.88 | 1.02 | 1510.0 |
