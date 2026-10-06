# Databricks notebook source
# MAGIC %md
# MAGIC # E07 · Databricks App "Plant Health Live"
# MAGIC
# MAGIC **What was built.** A FastAPI backend with a vanilla-JS single page (`src/app/`), deployed with the bundle as app
# MAGIC `pdm-plant-health-live`. Resources: Lakebase database (postgres), Model Serving endpoint, Genie space, SQL warehouse.
# MAGIC Endpoints: `/api/stations` (live grid from Lakebase), `/api/stations/{id}/history`, `/api/inject`, `/api/work_orders`,
# MAGIC `/api/work_orders/{id}/complete`, `/api/whatif` (Model Serving), `/api/genie` (Genie Conversation API), `/api/health`.
# MAGIC
# MAGIC **What this notebook proves.** The app is deployed and running with its resources and service principal, and the
# MAGIC data it wrote (work orders, fault and repair commands from the app user) exists in Lakebase and, via Lakehouse Sync,
# MAGIC in Unity Catalog. The full click-through via the app's HTTP API is recorded in `evidence/08_app/e2e_fault_injection.md`.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · App, compute, service principal and resources

# COMMAND ----------

app = w.apps.get(APP_NAME)
show({"name": app.name, "url": app.url, "app_status": app.app_status.state.value, "compute": app.compute_status.state.value,
      "service_principal": app.service_principal_name, "service_principal_client_id": app.service_principal_client_id,
      "active_deployment": {"id": app.active_deployment.deployment_id, "state": app.active_deployment.status.state.value,
                            "source": app.active_deployment.source_code_path, "updated": app.active_deployment.update_time},
      "resources": [r.as_dict() for r in app.resources]})

# COMMAND ----------

for d in list(w.apps.list_deployments(APP_NAME))[:5]:
    print(d.deployment_id, d.status.state.value, d.create_time)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Calling the app API from this notebook
# MAGIC Databricks Apps require an OAuth token; notebook credentials may be rejected. The outcome is printed either way.

# COMMAND ----------

import requests
try:
    headers = w.config.authenticate()
    r = requests.get(app.url + "/api/health", headers=headers, timeout=30)
    print("GET /api/health ->", r.status_code, r.text[:300])
    r = requests.get(app.url + "/api/stations", headers=headers, timeout=30)
    d = r.json() if r.ok else None
    print("GET /api/stations ->", r.status_code, {k: d[k] for k in ("data_age_s", "lakebase_query_ms")} if d else r.text[:200],
          "| stations:", len(d["stations"]) if d else None)
except Exception as e:
    print("App API call from notebook not possible with notebook credentials:", type(e).__name__, str(e)[:200])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · What the app wrote: work orders and commands (Lakebase, then UC via Lakehouse Sync)

# COMMAND ----------

conn = pg()
pg_table(conn, """SELECT work_order_id, station_id, priority, status, failure_probability, risk_band, top_signal,
                         created_by, created_at, completed_at FROM pdm_ops.work_orders ORDER BY work_order_id""")
pg_table(conn, """SELECT command_id, command, station_id, failure_mode, requested_by, status, requested_at, applied_at,
                         round(extract(epoch FROM applied_at - requested_at)::numeric, 2) AS seconds_to_apply
                  FROM pdm_ops.sim_commands ORDER BY command_id""")
display(spark.sql("SELECT * FROM pdm_ops.work_orders_current ORDER BY work_order_id"))
display(spark.sql("""SELECT Status, MEASURE(`Work Orders`) AS work_orders, MEASURE(`Avg Minutes To Complete`) AS avg_minutes_to_complete
                     FROM pdm_ops.work_order_metrics GROUP BY ALL"""))
