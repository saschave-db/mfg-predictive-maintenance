# Executed notebook: E04_lakebase

Exported from Databricks job run `980301348000608` (task `E04_lakebase`, task run `213085373190640`).

Result: **SUCCESS** · start 2026-10-06T18:02:18.080000+00:00 · end 2026-10-06T18:03:07.992000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


# E04 · Lakebase: OLTP tables, continuous synced table, Lakehouse Sync back to UC

**What was built.**
* Lakebase Autoscaling project `pdm-demo` (Postgres 17), endpoint `primary`.
* OLTP tables in Postgres schema `pdm_ops`: `work_orders` (written by the app) and `sim_commands` (written by the app,
  polled by the Zerobus simulator for fault injection and repairs). DDL: `src/lakebase/01_oltp_schema.sql`.
* **Continuous synced table** UC `pdm_core.station_risk_scores` -> Postgres `pdm_live.station_risk_scores`
  (PK `station_id, window_end`). The app reads the latest row per station from here.
* **Lakehouse Sync** (CDC) Postgres `pdm_ops` -> UC `pdm_ops.lb_work_orders_history`, `lb_sim_commands_history`.
* The app's Postgres role has least-privilege grants (`src/lakebase/02_app_grants.sql`).

**What this notebook proves.** It connects to Postgres from this notebook with a short-lived OAuth token and shows the
tables, grants, row counts, and the freshness of the synced table compared with its Delta source.

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
import time
spark.sql(f"USE CATALOG {CATALOG}")
```

Output:

```text
{"text/plain": "DataFrame[]"}
```

## 1 · Project, branch and endpoint

```python
proj = w.postgres.get_project(name="projects/pdm-demo")
ep = w.postgres.get_endpoint(name=LAKEBASE_ENDPOINT)
show({"project": proj.name, "display_name": getattr(proj.status, "display_name", None) or getattr(proj.spec, "display_name", None),
      "endpoint": ep.name, "state": ep.status.current_state.value, "host": ep.status.hosts.host,
      "min_cu": ep.status.autoscaling_limit_min_cu, "max_cu": ep.status.autoscaling_limit_max_cu})
```

Output:

```text
{
  "project": "projects/pdm-demo",
  "display_name": "Predictive maintenance demo (synthetic)",
  "endpoint": "projects/pdm-demo/branches/production/endpoints/primary",
  "state": "ACTIVE",
  "host": "ep-autumn-paper-d8fiis3p.database.us-east-2.cloud.databricks.com",
  "min_cu": 1.0,
  "max_cu": 1.0
}
```

```python
conn = pg()
pg_table(conn, "SELECT version() AS postgres_version, current_user, now() AS server_time")
```

Output:

| postgres_version | current_user | server_time |
|---|---|---|
| PostgreSQL 17.11 (fcae950) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit | sascha.vetter@databricks.com | 2026-10-06 18:02:32.047970+00:00 |

Output:

```text
{"text/plain": "[['PostgreSQL 17.11 (fcae950) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit',\n  'sascha.vetter@databricks.com',\n  datetime.datetime(2026, 10, 6, 18, 2, 32, 47970, tzinfo=datetime.timezone.utc)]]"}
```

## 2 · Tables in Postgres and their row counts

```python
pg_table(conn, """SELECT table_schema, table_name, table_type FROM information_schema.tables
                  WHERE table_schema IN ('pdm_ops', 'pdm_live') ORDER BY 1, 2""")
pg_table(conn, """SELECT 'pdm_ops.work_orders' AS t, count(*) FROM pdm_ops.work_orders
                  UNION ALL SELECT 'pdm_ops.sim_commands', count(*) FROM pdm_ops.sim_commands
                  UNION ALL SELECT 'pdm_live.station_risk_scores', count(*) FROM pdm_live.station_risk_scores""")
```

Output:

| table_schema | table_name | table_type |
|---|---|---|
| pdm_live | station_risk_scores | BASE TABLE |
| pdm_ops | sim_commands | BASE TABLE |
| pdm_ops | work_orders | BASE TABLE |
| t | count |
|---|---|
| pdm_ops.work_orders | 2 |
| pdm_ops.sim_commands | 4 |
| pdm_live.station_risk_scores | 48384 |

Output:

```text
{"text/plain": "[['pdm_ops.work_orders', 2],\n ['pdm_ops.sim_commands', 4],\n ['pdm_live.station_risk_scores', 48384]]"}
```

## 3 · Least-privilege grants for the app's Postgres role

```python
app_role = w.apps.get(APP_NAME).service_principal_client_id
print("app role:", app_role)
pg_table(conn, """SELECT table_schema, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privileges
                  FROM information_schema.role_table_grants WHERE grantee = :r GROUP BY 1, 2 ORDER BY 1, 2""", {"r": app_role})
```

Output:

```text
app role: 2a9b01a6-1050-4c7d-b389-45351bf8e97b
| table_schema | table_name | privileges |
|---|---|---|
| pdm_live | station_risk_scores | SELECT |
| pdm_ops | sim_commands | INSERT,SELECT |
| pdm_ops | work_orders | INSERT,SELECT,UPDATE |
```

Output:

```text
{"text/plain": "[['pdm_live', 'station_risk_scores', 'SELECT'],\n ['pdm_ops', 'sim_commands', 'INSERT,SELECT'],\n ['pdm_ops', 'work_orders', 'INSERT,SELECT,UPDATE']]"}
```

## 4 · Continuous synced table: status and freshness (Delta source vs Postgres copy)

```python
st = w.postgres.get_synced_table(name=f"synced_tables/{CATALOG}.pdm_live.station_risk_scores")
show({"synced_table": st.name, "state": st.status.detailed_state.value, "message": st.status.message,
      "last_sync": st.status.last_sync.as_dict() if st.status.last_sync else None, "sync_pipeline_id": st.status.pipeline_id})
sp = w.pipelines.get(st.status.pipeline_id)  # the managed sync pipeline
print("sync pipeline:", sp.name, "| state:", sp.state.value, "| continuous:", sp.spec.continuous)
print("synced from (UC source), as created: pdm_core.station_risk_scores, primary key (station_id, window_end), CONTINUOUS")
```

Output:

```text
{
  "synced_table": "synced_tables/serverless_stable_am1uc2_catalog.pdm_live.station_risk_scores",
  "state": "SYNCED_TABLE_ONLINE_CONTINUOUS_UPDATE",
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-serverless-stable-am1uc2.cloud.databricks.com#joblist/pipelines/5135c1d5-fce7-4893-898c-d902dc34a0ea/updates/8d9b79e6-dcc4-4a5e-a3ce-dde8fa89e270.",
  "last_sync": {
    "delta_table_sync_info": {
      "delta_commit_time": "2026-10-06T18:02:28Z",
      "delta_commit_version": 616
    },
    "sync_end_time": "2026-10-06T18:02:32.256115Z",
    "sync_start_time": "2026-10-06T18:02:31.489313Z"
  },
  "sync_pipeline_id": "5135c1d5-fce7-4893-898c-d902dc34a0ea"
}
sync pipeline: Synced table: serverless_stable_am1uc2_catalog.pdm_live.station_risk_scores sbgS40 | state: RUNNING | continuous: True
synced from (UC source), as created: pdm_core.station_risk_scores, primary key (station_id, window_end), CONTINUOUS
```

```python
for i in range(3):
    uc = spark.sql("SELECT max(window_end) AS newest, count(*) AS n FROM pdm_core.station_risk_scores").first()
    pgr = conn.run("SELECT max(window_end), count(*), now() FROM pdm_live.station_risk_scores")[0]
    print(f"check {i + 1}: Delta newest window {uc.newest} ({uc.n} rows) | Postgres newest window {pgr[0]} ({pgr[1]} rows) at {pgr[2]}")
    time.sleep(10) if i < 2 else None
```

Output:

```text
check 1: Delta newest window 2026-10-06 18:01:50 (48480 rows) | Postgres newest window 2026-10-06 18:01:50+00:00 (48480 rows) at 2026-10-06 18:02:36.383909+00:00
check 2: Delta newest window 2026-10-06 18:02:00 (48576 rows) | Postgres newest window 2026-10-06 18:02:00+00:00 (48576 rows) at 2026-10-06 18:02:47.585484+00:00
check 3: Delta newest window 2026-10-06 18:02:10 (48672 rows) | Postgres newest window 2026-10-06 18:02:10+00:00 (48672 rows) at 2026-10-06 18:02:58.675462+00:00
```

## 5 · The app's read query, timed in Postgres
Latest risk row per station via `DISTINCT ON` over the primary-key index.

```python
t0 = time.perf_counter()
pg_table(conn, """SELECT station_id, window_end, failure_probability, risk_band, top_signal
                  FROM (SELECT DISTINCT ON (station_id) * FROM pdm_live.station_risk_scores
                        WHERE window_end > now() - interval '10 minutes' ORDER BY station_id, window_end DESC) latest
                  ORDER BY failure_probability DESC""", limit=8)
print(f"query time incl. network from notebook: {(time.perf_counter() - t0) * 1000:.0f} ms")
pg_table(conn, """EXPLAIN (ANALYZE, COSTS OFF) SELECT DISTINCT ON (station_id) * FROM pdm_live.station_risk_scores
                  WHERE window_end > now() - interval '10 minutes' ORDER BY station_id, window_end DESC""", limit=15)
```

Output:

| station_id | window_end | failure_probability | risk_band | top_signal |
|---|---|---|---|---|
| PLT-E-C03 | 2026-10-06 18:02:10+00:00 | 0.9995 | HIGH | bearing_temp_c |
| PLT-N-B06 | 2026-10-06 18:02:10+00:00 | 0.9984 | HIGH | vibration_rms |
| PLT-N-C08 | 2026-10-06 18:02:10+00:00 | 0.998 | HIGH | vibration_rms |
| PLT-N-A05 | 2026-10-06 18:02:10+00:00 | 0.8804 | HIGH | vibration_rms |
| PLT-N-C03 | 2026-10-06 18:02:10+00:00 | 0.8048 | HIGH | vibration_rms |
| PLT-N-D03 | 2026-10-06 18:02:10+00:00 | 0.6492 | ELEVATED | vibration_rms |
| PLT-S-B02 | 2026-10-06 18:02:10+00:00 | 0.488 | ELEVATED | vibration_rms |
| PLT-N-B03 | 2026-10-06 18:02:10+00:00 | 0.3927 | NORMAL | vibration_rms |
... 88 more rows
query time incl. network from notebook: 33 ms
| QUERY PLAN |
|---|
| Unique (actual time=18.739..19.272 rows=96 loops=1) |
|   ->  Sort (actual time=18.738..18.954 rows=5376 loops=1) |
|         Sort Key: station_risk_scores.station_id, station_risk_scores.window_end DESC |
|         Sort Method: quicksort  Memory: 2838kB |
|         ->  Seq Scan on partition_49197 station_risk_scores (actual time=8.768..9.522 rows=5376 loops=1) |
|               Filter: (window_end > (now() - '00:10:00'::interval)) |
|               Rows Removed by Filter: 43296 |
| Planning Time: 0.236 ms |
| Execution Time: 19.371 ms |

Output:

```text
{"text/plain": "[['Unique (actual time=18.739..19.272 rows=96 loops=1)'],\n ['  ->  Sort (actual time=18.738..18.954 rows=5376 loops=1)'],\n ['        Sort Key: station_risk_scores.station_id, station_risk_scores.window_end DESC'],\n ['        Sort Method: quicksort  Memory: 2838kB'],\n ['        ->  Seq Scan on partition_49197 station_risk_scores (actual time=8.768..9.522 rows=5376 loops=1)'],\n [\"              Filter: (window_end > (now() - '00:10:00'::interval))\"],\n ['              Rows Removed by Filter: 43296'],\n ['Planning Time: 0.236 ms'],\n ['Execution Time: 19.371 ms']]"}
```

## 6 · OLTP contents and Lakehouse Sync back to Unity Catalog
The same rows appear in UC as CDC history (`_pg_change_type`, `_pg_lsn`) without any job or pipeline written by us.

```python
pg_table(conn, "SELECT * FROM pdm_ops.work_orders ORDER BY work_order_id DESC", limit=10)
pg_table(conn, "SELECT * FROM pdm_ops.sim_commands ORDER BY command_id DESC", limit=10)
display(spark.sql("""SELECT _pg_change_type, _pg_lsn, _timestamp, work_order_id, station_id, status, priority, failure_probability
                     FROM pdm_ops.lb_work_orders_history ORDER BY _pg_lsn"""))
display(spark.sql("SELECT * FROM pdm_ops.work_orders_current ORDER BY work_order_id"))
```

Output:

| work_order_id | station_id | plant_id | line_id | priority | status | failure_probability | risk_band | top_signal | description | assigned_technician_id | created_by | created_at | updated_at | completed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | PLT-S-B06 | PLT-S | PLT-S-B | P1 | completed | 0.8876 | HIGH | vibration_rms | E08 notebook: predicted bearing wear |  | sascha.vetter@databricks.com | 2026-10-06 17:57:26.883429+00:00 | 2026-10-06 17:57:46.897278+00:00 | 2026-10-06 17:57:46.897278+00:00 |
| 1 | PLT-E-A03 | PLT-E | PLT-E-A | P1 | completed | 0.7868 | HIGH | motor_current_a | E2E test: overheating alert |  | sascha.vetter@databricks.com | 2026-10-06 17:16:25.838121+00:00 | 2026-10-06 17:17:43.289537+00:00 | 2026-10-06 17:17:43.289537+00:00 |
| command_id | command | station_id | failure_mode | requested_by | status | requested_at | applied_at |
|---|---|---|---|---|---|---|---|
| 4 | repair | PLT-S-B06 |  | sascha.vetter@databricks.com | applied | 2026-10-06 17:57:46.905634+00:00 | 2026-10-06 17:57:47.001418+00:00 |
| 3 | inject_fault | PLT-S-B06 | bearing_wear | sascha.vetter@databricks.com | applied | 2026-10-06 17:51:52.893947+00:00 | 2026-10-06 17:51:53.002039+00:00 |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | applied | 2026-10-06 17:17:43.295412+00:00 | 2026-10-06 17:17:45.001512+00:00 |
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | applied | 2026-10-06 17:12:38.582498+00:00 | 2026-10-06 17:12:39.001621+00:00 |

Output:

| _pg_change_type | _pg_lsn | _timestamp | work_order_id | station_id | status | priority | failure_probability |
|---|---|---|---|---|---|---|---|
| insert | 59450264 | 2026-10-06T17:16:26.509 | 1 | PLT-E-A03 | open | P1 | 0.7868 |
| update_preimage | 60162312 | 2026-10-06T17:17:43.290 | 1 | PLT-E-A03 | open | P1 | 0.7868 |
| update_postimage | 60162312 | 2026-10-06T17:17:43.290 | 1 | PLT-E-A03 | completed | P1 | 0.7868 |
| insert | 90103520 | 2026-10-06T17:57:26.883 | 2 | PLT-S-B06 | open | P1 | 0.8876 |
| update_preimage | 90338344 | 2026-10-06T17:57:46.897 | 2 | PLT-S-B06 | open | P1 | 0.8876 |
| update_postimage | 90338344 | 2026-10-06T17:57:46.897 | 2 | PLT-S-B06 | completed | P1 | 0.8876 |

Output:

| work_order_id | station_id | plant_id | line_id | priority | status | failure_probability | risk_band | top_signal | description | assigned_technician_id | created_by | created_at | updated_at | completed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLT-E-A03 | PLT-E | PLT-E-A | P1 | completed | 0.7868 | HIGH | motor_current_a | E2E test: overheating alert |  | sascha.vetter@databricks.com | 2026-10-06T17:16:25.838Z | 2026-10-06T17:17:43.289Z | 2026-10-06T17:17:43.289Z |
| 2 | PLT-S-B06 | PLT-S | PLT-S-B | P1 | completed | 0.8876 | HIGH | vibration_rms | E08 notebook: predicted bearing wear |  | sascha.vetter@databricks.com | 2026-10-06T17:57:26.883Z | 2026-10-06T17:57:46.897Z | 2026-10-06T17:57:46.897Z |
