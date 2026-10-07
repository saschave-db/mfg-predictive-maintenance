# Executed notebook: E04_lakebase

Exported from Databricks job run `994447175034582` (task `E04_lakebase`, task run `136200307398885`).

Result: **SUCCESS** · start 2026-10-07T22:59:30.085000+00:00 · end 2026-10-07T23:00:19.252000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


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
| PostgreSQL 17.11 (fcae950) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit | sascha.vetter@databricks.com | 2026-10-07 22:59:43.969493+00:00 |

Output:

```text
{"text/plain": "[['PostgreSQL 17.11 (fcae950) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit',\n  'sascha.vetter@databricks.com',\n  datetime.datetime(2026, 10, 7, 22, 59, 43, 969493, tzinfo=datetime.timezone.utc)]]"}
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
| pdm_ops.work_orders | 3 |
| pdm_ops.sim_commands | 6 |
| pdm_live.station_risk_scores | 81888 |

Output:

```text
{"text/plain": "[['pdm_ops.work_orders', 3],\n ['pdm_ops.sim_commands', 6],\n ['pdm_live.station_risk_scores', 81888]]"}
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
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-serverless-stable-am1uc2.cloud.databricks.com#joblist/pipelines/5135c1d5-fce7-4893-898c-d902dc34a0ea/updates/b2ea1b10-07ae-44f4-8dde-08b95e305402.",
  "last_sync": {
    "delta_table_sync_info": {
      "delta_commit_time": "2026-10-07T22:59:35Z",
      "delta_commit_version": 1365
    },
    "sync_end_time": "2026-10-07T22:59:37.222332Z",
    "sync_start_time": "2026-10-07T22:59:36.949660Z"
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
check 1: Delta newest window 2026-10-07 22:59:00 (81984 rows) | Postgres newest window 2026-10-07 22:59:00+00:00 (81984 rows) at 2026-10-07 22:59:47.376189+00:00
check 2: Delta newest window 2026-10-07 22:59:00 (81984 rows) | Postgres newest window 2026-10-07 22:59:00+00:00 (81984 rows) at 2026-10-07 22:59:58.599044+00:00
check 3: Delta newest window 2026-10-07 22:59:20 (82176 rows) | Postgres newest window 2026-10-07 22:59:20+00:00 (82176 rows) at 2026-10-07 23:00:09.872485+00:00
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
| PLT-S-A06 | 2026-10-07 22:59:20+00:00 | 0.9972 | HIGH | motor_current_a |
| PLT-S-A04 | 2026-10-07 22:59:20+00:00 | 0.9968 | HIGH | vibration_rms |
| PLT-S-D04 | 2026-10-07 22:59:20+00:00 | 0.7934 | HIGH | vibration_rms |
| PLT-N-D08 | 2026-10-07 22:59:20+00:00 | 0.5515 | ELEVATED | acoustic_db |
| PLT-S-C02 | 2026-10-07 22:59:20+00:00 | 0.3209 | NORMAL | vibration_rms |
| PLT-E-B05 | 2026-10-07 22:59:20+00:00 | 0.265 | NORMAL | hydraulic_pressure_bar |
| PLT-S-B01 | 2026-10-07 22:59:20+00:00 | 0.2248 | NORMAL | vibration_rms |
| PLT-S-D07 | 2026-10-07 22:59:20+00:00 | 0.1908 | NORMAL | vibration_rms |
... 88 more rows
query time incl. network from notebook: 26 ms
| QUERY PLAN |
|---|
| Unique (actual time=0.122..13.077 rows=96 loops=1) |
|   ->  Incremental Sort (actual time=0.122..12.821 rows=4608 loops=1) |
|         Sort Key: station_risk_scores.station_id, station_risk_scores.window_end DESC |
|         Presorted Key: station_risk_scores.station_id |
|         Full-sort Groups: 96  Sort Method: quicksort  Average Memory: 48kB  Peak Memory: 48kB |
|         ->  Index Scan using "__db_tmp_791a7023-b483-4e22-8269-ee3a5b3a99fa_pkey" on partition_49197 station_risk_scores (actual time=0.029..9.439 rows=4608 loops=1) |
|               Index Cond: (window_end > (now() - '00:10:00'::interval)) |
| Planning Time: 0.308 ms |
| Execution Time: 13.108 ms |

Output:

```text
{"text/plain": "[['Unique (actual time=0.122..13.077 rows=96 loops=1)'],\n ['  ->  Incremental Sort (actual time=0.122..12.821 rows=4608 loops=1)'],\n ['        Sort Key: station_risk_scores.station_id, station_risk_scores.window_end DESC'],\n ['        Presorted Key: station_risk_scores.station_id'],\n ['        Full-sort Groups: 96  Sort Method: quicksort  Average Memory: 48kB  Peak Memory: 48kB'],\n ['        ->  Index Scan using \"__db_tmp_791a7023-b483-4e22-8269-ee3a5b3a99fa_pkey\" on partition_49197 station_risk_scores (actual time=0.029..9.439 rows=4608 loops=1)'],\n [\"              Index Cond: (window_end > (now() - '00:10:00'::interval))\"],\n ['Planning Time: 0.308 ms'],\n ['Execution Time: 13.108 ms']]"}
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
| 3 | PLT-N-C07 | PLT-N | PLT-N-C | P2 | completed | 0.9898 | HIGH | bearing_temp_c | Predicted bearing_temp_c issue |  | sascha.vetter@databricks.com | 2026-10-07 22:57:59.169938+00:00 | 2026-10-07 22:58:12.718962+00:00 | 2026-10-07 22:58:12.718962+00:00 |
| 2 | PLT-S-B06 | PLT-S | PLT-S-B | P1 | completed | 0.8876 | HIGH | vibration_rms | E08 notebook: predicted bearing wear |  | sascha.vetter@databricks.com | 2026-10-06 17:57:26.883429+00:00 | 2026-10-06 17:57:46.897278+00:00 | 2026-10-06 17:57:46.897278+00:00 |
| 1 | PLT-E-A03 | PLT-E | PLT-E-A | P1 | completed | 0.7868 | HIGH | motor_current_a | E2E test: overheating alert |  | sascha.vetter@databricks.com | 2026-10-06 17:16:25.838121+00:00 | 2026-10-06 17:17:43.289537+00:00 | 2026-10-06 17:17:43.289537+00:00 |
| command_id | command | station_id | failure_mode | requested_by | status | requested_at | applied_at |
|---|---|---|---|---|---|---|---|
| 6 | repair | PLT-N-C07 |  | sascha.vetter@databricks.com | applied | 2026-10-07 22:58:12.724309+00:00 | 2026-10-07 22:58:13.001443+00:00 |
| 5 | inject_fault | PLT-S-A04 | overheating | sascha.vetter@databricks.com | applied | 2026-10-07 22:57:32.212895+00:00 | 2026-10-07 22:57:33.001346+00:00 |
| 4 | repair | PLT-S-B06 |  | sascha.vetter@databricks.com | applied | 2026-10-06 17:57:46.905634+00:00 | 2026-10-06 17:57:47.001418+00:00 |
| 3 | inject_fault | PLT-S-B06 | bearing_wear | sascha.vetter@databricks.com | applied | 2026-10-06 17:51:52.893947+00:00 | 2026-10-06 17:51:53.002039+00:00 |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | applied | 2026-10-06 17:17:43.295412+00:00 | 2026-10-06 17:17:45.001512+00:00 |
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | applied | 2026-10-06 17:12:38.582498+00:00 | 2026-10-06 17:12:39.001621+00:00 |

Output:

| _pg_change_type | _pg_lsn | _timestamp | work_order_id | station_id | status | priority | failure_probability |
|---|---|---|---|---|---|---|---|
| insert | 59450264 | 2026-10-06T17:16:26.509 | 1 | PLT-E-A03 | open | P1 | 0.7868 |
| update_postimage | 60162312 | 2026-10-06T17:17:43.290 | 1 | PLT-E-A03 | completed | P1 | 0.7868 |
| update_preimage | 60162312 | 2026-10-06T17:17:43.290 | 1 | PLT-E-A03 | open | P1 | 0.7868 |
| insert | 90103520 | 2026-10-06T17:57:26.883 | 2 | PLT-S-B06 | open | P1 | 0.8876 |
| update_postimage | 90338344 | 2026-10-06T17:57:46.897 | 2 | PLT-S-B06 | completed | P1 | 0.8876 |
| update_preimage | 90338344 | 2026-10-06T17:57:46.897 | 2 | PLT-S-B06 | open | P1 | 0.8876 |
| insert | 137451520 | 2026-10-07T22:57:59.518 | 3 | PLT-N-C07 | open | P2 | 0.9898 |
| update_preimage | 137452704 | 2026-10-07T22:58:12.719 | 3 | PLT-N-C07 | open | P2 | 0.9898 |
| update_postimage | 137452704 | 2026-10-07T22:58:12.719 | 3 | PLT-N-C07 | completed | P2 | 0.9898 |

Output:

| work_order_id | station_id | plant_id | line_id | priority | status | failure_probability | risk_band | top_signal | description | assigned_technician_id | created_by | created_at | updated_at | completed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLT-E-A03 | PLT-E | PLT-E-A | P1 | completed | 0.7868 | HIGH | motor_current_a | E2E test: overheating alert |  | sascha.vetter@databricks.com | 2026-10-06T17:16:25.838Z | 2026-10-06T17:17:43.289Z | 2026-10-06T17:17:43.289Z |
| 2 | PLT-S-B06 | PLT-S | PLT-S-B | P1 | completed | 0.8876 | HIGH | vibration_rms | E08 notebook: predicted bearing wear |  | sascha.vetter@databricks.com | 2026-10-06T17:57:26.883Z | 2026-10-06T17:57:46.897Z | 2026-10-06T17:57:46.897Z |
| 3 | PLT-N-C07 | PLT-N | PLT-N-C | P2 | completed | 0.9898 | HIGH | bearing_temp_c | Predicted bearing_temp_c issue |  | sascha.vetter@databricks.com | 2026-10-07T22:57:59.169Z | 2026-10-07T22:58:12.718Z | 2026-10-07T22:58:12.718Z |

## 7 · Timed database round trips (write + read) from this notebook
A temporary table lives only in this session, so the test touches no demo data.

```python
conn.run("CREATE TEMP TABLE rt_probe (id int PRIMARY KEY, payload text, at timestamptz DEFAULT now())")
print("| iteration | INSERT ms | SELECT ms | value read back |\n|---|---|---|---|")
for i in range(1, 6):
    t0 = time.perf_counter()
    conn.run("INSERT INTO rt_probe (id, payload) VALUES (:i, :p)", i=i, p=f"probe-{i}")
    t1 = time.perf_counter()
    v = conn.run("SELECT payload FROM rt_probe WHERE id = :i", i=i)[0][0]
    t2 = time.perf_counter()
    print(f"| {i} | {(t1 - t0) * 1000:.1f} | {(t2 - t1) * 1000:.1f} | {v} |")
conn.run("DROP TABLE rt_probe")
```

Output:

| iteration | INSERT ms | SELECT ms | value read back |
|---|---|---|---|
| 1 | 13.8 | 13.5 | probe-1 |
| 2 | 12.7 | 12.1 | probe-2 |
| 3 | 11.8 | 11.8 | probe-3 |
| 4 | 12.3 | 12.1 | probe-4 |
| 5 | 11.7 | 11.8 | probe-5 |
