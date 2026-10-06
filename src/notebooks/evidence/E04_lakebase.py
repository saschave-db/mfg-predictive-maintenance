# Databricks notebook source
# MAGIC %md
# MAGIC # E04 · Lakebase: OLTP tables, continuous synced table, Lakehouse Sync back to UC
# MAGIC
# MAGIC **What was built.**
# MAGIC * Lakebase Autoscaling project `pdm-demo` (Postgres 17), endpoint `primary`.
# MAGIC * OLTP tables in Postgres schema `pdm_ops`: `work_orders` (written by the app) and `sim_commands` (written by the app,
# MAGIC   polled by the Zerobus simulator for fault injection and repairs). DDL: `src/lakebase/01_oltp_schema.sql`.
# MAGIC * **Continuous synced table** UC `pdm_core.station_risk_scores` -> Postgres `pdm_live.station_risk_scores`
# MAGIC   (PK `station_id, window_end`). The app reads the latest row per station from here.
# MAGIC * **Lakehouse Sync** (CDC) Postgres `pdm_ops` -> UC `pdm_ops.lb_work_orders_history`, `lb_sim_commands_history`.
# MAGIC * The app's Postgres role has least-privilege grants (`src/lakebase/02_app_grants.sql`).
# MAGIC
# MAGIC **What this notebook proves.** It connects to Postgres from this notebook with a short-lived OAuth token and shows the
# MAGIC tables, grants, row counts, and the freshness of the synced table compared with its Delta source.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import time
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Project, branch and endpoint

# COMMAND ----------

proj = w.postgres.get_project(name="projects/pdm-demo")
ep = w.postgres.get_endpoint(name=LAKEBASE_ENDPOINT)
show({"project": proj.name, "display_name": getattr(proj.status, "display_name", None) or getattr(proj.spec, "display_name", None),
      "endpoint": ep.name, "state": ep.status.current_state.value, "host": ep.status.hosts.host,
      "min_cu": ep.status.autoscaling_limit_min_cu, "max_cu": ep.status.autoscaling_limit_max_cu})

# COMMAND ----------

conn = pg()
pg_table(conn, "SELECT version() AS postgres_version, current_user, now() AS server_time")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Tables in Postgres and their row counts

# COMMAND ----------

pg_table(conn, """SELECT table_schema, table_name, table_type FROM information_schema.tables
                  WHERE table_schema IN ('pdm_ops', 'pdm_live') ORDER BY 1, 2""")
pg_table(conn, """SELECT 'pdm_ops.work_orders' AS t, count(*) FROM pdm_ops.work_orders
                  UNION ALL SELECT 'pdm_ops.sim_commands', count(*) FROM pdm_ops.sim_commands
                  UNION ALL SELECT 'pdm_live.station_risk_scores', count(*) FROM pdm_live.station_risk_scores""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Least-privilege grants for the app's Postgres role

# COMMAND ----------

app_role = w.apps.get(APP_NAME).service_principal_client_id
print("app role:", app_role)
pg_table(conn, """SELECT table_schema, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privileges
                  FROM information_schema.role_table_grants WHERE grantee = :r GROUP BY 1, 2 ORDER BY 1, 2""", {"r": app_role})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Continuous synced table: status and freshness (Delta source vs Postgres copy)

# COMMAND ----------

st = w.postgres.get_synced_table(name=f"synced_tables/{CATALOG}.pdm_live.station_risk_scores")
show({"synced_table": st.name, "state": st.status.detailed_state.value, "message": st.status.message,
      "last_sync": st.status.last_sync.as_dict() if st.status.last_sync else None, "sync_pipeline_id": st.status.pipeline_id})
sp = w.pipelines.get(st.status.pipeline_id)  # the managed sync pipeline
print("sync pipeline:", sp.name, "| state:", sp.state.value, "| continuous:", sp.spec.continuous)
print("synced from (UC source), as created: pdm_core.station_risk_scores, primary key (station_id, window_end), CONTINUOUS")

# COMMAND ----------

for i in range(3):
    uc = spark.sql("SELECT max(window_end) AS newest, count(*) AS n FROM pdm_core.station_risk_scores").first()
    pgr = conn.run("SELECT max(window_end), count(*), now() FROM pdm_live.station_risk_scores")[0]
    print(f"check {i + 1}: Delta newest window {uc.newest} ({uc.n} rows) | Postgres newest window {pgr[0]} ({pgr[1]} rows) at {pgr[2]}")
    time.sleep(10) if i < 2 else None

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · The app's read query, timed in Postgres
# MAGIC Latest risk row per station via `DISTINCT ON` over the primary-key index.

# COMMAND ----------

t0 = time.perf_counter()
pg_table(conn, """SELECT station_id, window_end, failure_probability, risk_band, top_signal
                  FROM (SELECT DISTINCT ON (station_id) * FROM pdm_live.station_risk_scores
                        WHERE window_end > now() - interval '10 minutes' ORDER BY station_id, window_end DESC) latest
                  ORDER BY failure_probability DESC""", limit=8)
print(f"query time incl. network from notebook: {(time.perf_counter() - t0) * 1000:.0f} ms")
pg_table(conn, """EXPLAIN (ANALYZE, COSTS OFF) SELECT DISTINCT ON (station_id) * FROM pdm_live.station_risk_scores
                  WHERE window_end > now() - interval '10 minutes' ORDER BY station_id, window_end DESC""", limit=15)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · OLTP contents and Lakehouse Sync back to Unity Catalog
# MAGIC The same rows appear in UC as CDC history (`_pg_change_type`, `_pg_lsn`) without any job or pipeline written by us.

# COMMAND ----------

pg_table(conn, "SELECT * FROM pdm_ops.work_orders ORDER BY work_order_id DESC", limit=10)
pg_table(conn, "SELECT * FROM pdm_ops.sim_commands ORDER BY command_id DESC", limit=10)
display(spark.sql("""SELECT _pg_change_type, _pg_lsn, _timestamp, work_order_id, station_id, status, priority, failure_probability
                     FROM pdm_ops.lb_work_orders_history ORDER BY _pg_lsn"""))
display(spark.sql("SELECT * FROM pdm_ops.work_orders_current ORDER BY work_order_id"))
