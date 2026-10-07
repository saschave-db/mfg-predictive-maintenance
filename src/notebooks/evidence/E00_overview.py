# Databricks notebook source
# MAGIC %md
# MAGIC # E00 · Evidence overview: live predictive maintenance on Databricks
# MAGIC
# MAGIC This notebook set proves, step by step, that the demo was built and runs on this workspace.
# MAGIC Every output below is produced live by querying the workspace (SDK calls, SQL on Unity Catalog, SQL on Lakebase).
# MAGIC All data is synthetic.
# MAGIC
# MAGIC ```
# MAGIC Simulator (96 stations, 1 Hz) --Zerobus--> pdm_raw.sensor_readings (Delta)
# MAGIC   --SDP continuous--> sensor_readings_clean -> station_risk_scores (windows + UC model in-stream) -> station_health_current
# MAGIC   --Lakebase continuous sync--> pdm_live.station_risk_scores (Postgres) --> Databricks App
# MAGIC App --> Lakebase pdm_ops.work_orders / sim_commands --Lakehouse Sync--> UC pdm_ops.lb_*_history
# MAGIC Metric views pdm_ops.*_metrics --> Genie agent;  UC model --> Model Serving pdm-station-risk --> App what-if
# MAGIC ```
# MAGIC
# MAGIC | Step | Notebook | What it proves |
# MAGIC |---|---|---|
# MAGIC | Data generation + ingestion | E01 | Zerobus writes from the gateway service principal land in a governed Delta table |
# MAGIC | ETL | E02 | Continuous SDP pipeline, expectations, freshness, lineage |
# MAGIC | ML | E03 | Registered model, metrics, in-stream scores reproducible with the registry and Model Serving |
# MAGIC | Lakebase | E04 | OLTP tables, synced table, freshness Delta vs Postgres, Lakehouse Sync back to UC |
# MAGIC | Governance | E05 | Grants, masks, row filter, tags, metric views; enforcement proven on the app's service principal (non-owner) |
# MAGIC | Genie | E06 | Agent configuration and live answers checked against reference SQL |
# MAGIC | App | E07 | App deployment, resources, and its writes to Lakebase |
# MAGIC | End to end | E08 | Live fault injected and traced to a HIGH alert, work order, repair, recovery |
# MAGIC | Source integrity | E09 | Deployed files are byte-identical to the committed source (SHA-256), full pipeline source printed |

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import datetime
print("evidence run at (UTC):", datetime.datetime.now(datetime.timezone.utc).isoformat())
print("workspace:", w.config.host)
print("run as:", w.current_user.me().user_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## State of every deployed resource
# MAGIC One line per resource, read from the workspace APIs at run time.

# COMMAND ----------

rows = []
p = w.pipelines.get(PIPELINE_ID)
rows.append(("SDP pipeline", p.name, f"state={p.state.value}, continuous={p.spec.continuous}, serverless={p.spec.serverless}"))
for j in w.jobs.list(name=None):
    if j.settings.name.startswith("pdm_"):
        last = next(iter(w.jobs.list_runs(job_id=j.job_id, limit=1)), None)
        rows.append(("Job", j.settings.name, f"job_id={j.job_id}, last run={last.state.result_state.value if last and last.state.result_state else (last.state.life_cycle_state.value if last else 'none')}"))
ep = w.serving_endpoints.get(SERVING_ENDPOINT)
rows.append(("Model Serving", ep.name, f"ready={ep.state.ready.value}, served={[(e.entity_name.split('.')[-1], e.entity_version) for e in ep.config.served_entities]}"))
app = w.apps.get(APP_NAME)
rows.append(("Databricks App", app.name, f"app={app.app_status.state.value}, compute={app.compute_status.state.value}, url={app.url}"))
lb = w.postgres.get_endpoint(name=LAKEBASE_ENDPOINT)
rows.append(("Lakebase endpoint", LAKEBASE_ENDPOINT, f"state={lb.status.current_state.value}"))
st = w.postgres.get_synced_table(name=f"synced_tables/{CATALOG}.pdm_live.station_risk_scores")
rows.append(("Lakebase synced table", f"{CATALOG}.pdm_live.station_risk_scores", f"state={st.status.detailed_state.value}"))
g = w.api_client.do("GET", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}")
rows.append(("Genie agent", g["title"], f"space_id={g['space_id']}"))
display(spark.createDataFrame(rows, "resource string, name string, status string"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Unity Catalog objects of the demo

# COMMAND ----------

display(spark.sql(f"""
SELECT table_schema, table_name, table_type, comment
FROM {CATALOG}.information_schema.tables
WHERE table_schema LIKE 'pdm_%' AND NOT startswith(table_name, '__') AND NOT startswith(table_name, 'event_log_')
ORDER BY table_schema, table_name"""))
