# Executed notebook: E01_zerobus_ingestion

Exported from Databricks job run `994447175034582` (task `E01_zerobus_ingestion`, task run `916008253330264`).

Result: **SUCCESS** · start 2026-10-07T22:56:54.424000+00:00 · end 2026-10-07T22:58:19.974000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


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
run 599986915233103: RUNNING  started 2026-10-07T22:49:11.550000
run 433290942380103: TERMINATED CANCELED started 2026-10-06T16:54:20.522000
run 320983066504714: TERMINATED CANCELED started 2026-10-05T22:27:17.055000
```

Output:

```text
/home/spark-e49c84ee-710a-4c82-a997-0c/.ipykernel/67/command-6364727878986308-2057826776:8: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
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
| 1790 | 2026-10-07T22:57:10.000Z | (not recorded) | WRITE | Zerobus |
| 1789 | 2026-10-07T22:57:05.000Z | (not recorded) | WRITE | Zerobus |
| 1788 | 2026-10-07T22:57:00.000Z | (not recorded) | WRITE | Zerobus |
| 1787 | 2026-10-07T22:56:55.000Z | (not recorded) | WRITE | Zerobus |
| 1786 | 2026-10-07T22:56:50.000Z | (not recorded) | WRITE | Zerobus |
| 1785 | 2026-10-07T22:56:45.000Z | (not recorded) | WRITE | Zerobus |
| 1784 | 2026-10-07T22:56:40.000Z | (not recorded) | WRITE | Zerobus |
| 1783 | 2026-10-07T22:56:35.000Z | (not recorded) | WRITE | Zerobus |
| 1782 | 2026-10-07T22:56:30.000Z | (not recorded) | WRITE | Zerobus |
| 1781 | 2026-10-07T22:56:25.000Z | (not recorded) | WRITE | Zerobus |

Output:

| engineInfo | operation | commits | first_commit | last_commit |
|---|---|---|---|---|
| Zerobus | WRITE | 1791 | 2026-10-05T22:07:30.000Z | 2026-10-07T22:57:30.000Z |
| Databricks-Runtime/19.9.x-aarch64-photon-scala2.13 | OPTIMIZE | 2 | 2026-10-06T17:15:44.000Z | 2026-10-06T21:46:23.000Z |
| Databricks-Runtime/19.8.x-aarch64-photon-scala2.13 | OPTIMIZE | 1 | 2026-10-05T22:53:49.000Z | 2026-10-05T22:53:49.000Z |
| Databricks-Runtime/19.9.x-aarch64-photon-scala2.13 | CREATE TABLE | 1 | 2026-10-05T21:57:47.000Z | 2026-10-05T21:57:47.000Z |

Output:

| zerobus_commits_last_10min | avg_seconds_between_commits |
|---|---|
| 98 | 1031.9 |

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
| gw-plt-e | 16224 | 32 | 27.0 | 2026-10-07T22:57:59.000Z | 2 |
| gw-plt-n | 16224 | 32 | 27.0 | 2026-10-07T22:57:59.000Z | 2 |
| gw-plt-s | 16224 | 32 | 27.0 | 2026-10-07T22:57:59.000Z | 2 |

Output:

| minute | rows | stations |
|---|---|---|
| 2026-10-07T22:49:00.000Z | 2592 | 96 |
| 2026-10-07T22:50:00.000Z | 5760 | 96 |
| 2026-10-07T22:51:00.000Z | 5760 | 96 |
| 2026-10-07T22:52:00.000Z | 5760 | 96 |
| 2026-10-07T22:53:00.000Z | 5760 | 96 |
| 2026-10-07T22:54:00.000Z | 5760 | 96 |
| 2026-10-07T22:55:00.000Z | 5760 | 96 |
| 2026-10-07T22:56:00.000Z | 5760 | 96 |
| 2026-10-07T22:57:00.000Z | 5760 | 96 |
| 2026-10-07T22:58:00.000Z | 480 | 96 |

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
| PLT-E-A01-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A01 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.964 | 45.144 | 32.545 | 1269.132 | 175.815 | 82.594 | 11.985 | gw-fw-3.2.1 |
| PLT-E-A02-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A02 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.602 | 54.169 | 18.659 | 9107.568 | 60.341 | 72.123 | 46.979 | gw-fw-3.2.1 |
| PLT-E-A03-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A03 | 2026-10-07T22:58:04.000Z | 1791413884 | 0.773 | 60.855 | 114.022 | 304.743 | 5.904 | 72.884 | 21.049 | gw-fw-3.2.1 |
| PLT-E-A04-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A04 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.017 | 39.316 | 10.68 | 3172.369 | 5.72 | 65.352 | 16.3 | gw-fw-3.2.1 |
| PLT-E-A05-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A05 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.285 | 40.046 | 7.399 | 1413.817 | 5.837 | 65.24 | 5.128 | gw-fw-3.2.1 |
| PLT-E-A06-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A06 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.539 | 47.225 | 17.849 | 9041.084 | 61.064 | 66.909 | 43.264 | gw-fw-3.2.1 |
| PLT-E-A07-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A07 | 2026-10-07T22:58:04.000Z | 1791413884 | 0.864 | 60.762 | 115.544 | 297.32 | 6.479 | 69.996 | 18.906 | gw-fw-3.2.1 |
| PLT-E-A08-1791413884 | gw-plt-e | PLT-E | PLT-E-A | PLT-E-A08 | 2026-10-07T22:58:04.000Z | 1791413884 | 1.799 | 46.472 | 30.185 | 1164.4 | 170.296 | 74.086 | 11.96 | gw-fw-3.2.1 |

Output:

| bronze_rows | distinct_event_ids | silver_rows |
|---|---|---|
| 863232 | 863232 | 862272 |

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
| PLT-S-A04 | robot_arm | 3.17 | 1.13 | 1.02 | 2956.0 |
| PLT-N-C07 | welder | 1.19 | 1.32 | 1.01 | 298.0 |
| PLT-S-D07 | welder | 1.28 | 1.08 | 0.98 | 290.0 |
| PLT-E-B01 | press | 1.13 | 0.97 | 0.98 | 1273.0 |
| PLT-S-C08 | press | 1.12 | 0.99 | 0.95 | 1214.0 |
| PLT-E-D05 | conveyor | 0.95 | 0.9 | 1.01 | 1509.0 |
| PLT-S-C02 | cnc_mill | 1.1 | 1.05 | 1.01 | 8840.0 |
| PLT-S-A06 | cnc_mill | 1.07 | 1.1 | 1.05 | 8960.0 |
| PLT-N-D06 | cnc_mill | 1.09 | 1.04 | 0.99 | 9028.0 |
| PLT-E-B03 | welder | 1.09 | 1.0 | 1.0 | 294.0 |
