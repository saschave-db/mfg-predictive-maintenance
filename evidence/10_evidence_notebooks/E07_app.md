# Executed notebook: E07_app

Exported from Databricks job run `980301348000608` (task `E07_app`, task run `820074943157191`).

Result: **SUCCESS** · start 2026-10-06T17:51:20.108000+00:00 · end 2026-10-06T17:51:39.961000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


# E07 · Databricks App "Plant Health Live"

**What was built.** A FastAPI backend with a vanilla-JS single page (`src/app/`), deployed with the bundle as app
`pdm-plant-health-live`. Resources: Lakebase database (postgres), Model Serving endpoint, Genie space, SQL warehouse.
Endpoints: `/api/stations` (live grid from Lakebase), `/api/stations/{id}/history`, `/api/inject`, `/api/work_orders`,
`/api/work_orders/{id}/complete`, `/api/whatif` (Model Serving), `/api/genie` (Genie Conversation API), `/api/health`.

**What this notebook proves.** The app is deployed and running with its resources and service principal, and the
data it wrote (work orders, fault and repair commands from the app user) exists in Lakebase and, via Lakehouse Sync,
in Unity Catalog. The full click-through via the app's HTTP API is recorded in `evidence/08_app/e2e_fault_injection.md`.

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
spark.sql(f"USE CATALOG {CATALOG}")
```

Output:

```text
{"text/plain": "DataFrame[]"}
```

## 1 · App, compute, service principal and resources

```python
app = w.apps.get(APP_NAME)
show({"name": app.name, "url": app.url, "app_status": app.app_status.state.value, "compute": app.compute_status.state.value,
      "service_principal": app.service_principal_name, "service_principal_client_id": app.service_principal_client_id,
      "active_deployment": {"id": app.active_deployment.deployment_id, "state": app.active_deployment.status.state.value,
                            "source": app.active_deployment.source_code_path, "updated": app.active_deployment.update_time},
      "resources": [r.as_dict() for r in app.resources]})
```

Output:

```text
{
  "name": "pdm-plant-health-live",
  "url": "https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com",
  "app_status": "RUNNING",
  "compute": "ACTIVE",
  "service_principal": "app-3jm8lb pdm-plant-health-live",
  "service_principal_client_id": "2a9b01a6-1050-4c7d-b389-45351bf8e97b",
  "active_deployment": {
    "id": "01f1c1a84e581cfd878dcbcf7c79a6a9",
    "state": "SUCCEEDED",
    "source": "/Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src/app",
    "updated": "2026-10-06T17:06:50Z"
  },
  "resources": [
    {
      "name": "postgres",
      "postgres": {
        "branch": "projects/pdm-demo/branches/production",
        "database": "projects/pdm-demo/branches/production/databases/databricks-postgres",
        "permission": "CAN_CONNECT_AND_CREATE"
      }
    },
    {
      "name": "serving",
      "serving_endpoint": {
        "name": "pdm-station-risk",
        "permission": "CAN_QUERY"
      }
    },
    {
      "genie_space": {
        "name": "Plant Maintenance Agent",
        "permission": "CAN_RUN",
        "space_id": "01f1c10d662111078cd7326dff1774c6"
      },
      "name": "genie"
    },
    {
      "name": "warehouse",
      "sql_warehouse": {
        "id": "fb9bc265e9f4578a",
        "permission": "CAN_USE"
      }
    }
  ]
}
```

```python
for d in list(w.apps.list_deployments(APP_NAME))[:5]:
    print(d.deployment_id, d.status.state.value, d.create_time)
```

Output:

```text
01f1c1a84e581cfd878dcbcf7c79a6a9 SUCCEEDED 2026-10-06T17:06:43Z
01f1c1a815781979a9120b9c6acba1e0 SUCCEEDED 2026-10-06T17:05:08Z
01f1c1a7e34112098bbec6673216bc6d SUCCEEDED 2026-10-06T17:03:44Z
```

## 2 · Calling the app API from this notebook
Databricks Apps require an OAuth token; notebook credentials may be rejected. The outcome is printed either way.

```python
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
```

Output:

```text
GET /api/health -> 401 {}
GET /api/stations -> 401 {} | stations: None
```

## 3 · What the app wrote: work orders and commands (Lakebase, then UC via Lakehouse Sync)

```python
conn = pg()
pg_table(conn, """SELECT work_order_id, station_id, priority, status, failure_probability, risk_band, top_signal,
                         created_by, created_at, completed_at FROM pdm_ops.work_orders ORDER BY work_order_id""")
pg_table(conn, """SELECT command_id, command, station_id, failure_mode, requested_by, status, requested_at, applied_at,
                         round(extract(epoch FROM applied_at - requested_at)::numeric, 2) AS seconds_to_apply
                  FROM pdm_ops.sim_commands ORDER BY command_id""")
display(spark.sql("SELECT * FROM pdm_ops.work_orders_current ORDER BY work_order_id"))
display(spark.sql("""SELECT Status, MEASURE(`Work Orders`) AS work_orders, MEASURE(`Avg Minutes To Complete`) AS avg_minutes_to_complete
                     FROM pdm_ops.work_order_metrics GROUP BY ALL"""))
```

Output:

| work_order_id | station_id | priority | status | failure_probability | risk_band | top_signal | created_by | created_at | completed_at |
|---|---|---|---|---|---|---|---|---|---|
| 1 | PLT-E-A03 | P1 | completed | 0.7868 | HIGH | motor_current_a | sascha.vetter@databricks.com | 2026-10-06 17:16:25.838121+00:00 | 2026-10-06 17:17:43.289537+00:00 |
| command_id | command | station_id | failure_mode | requested_by | status | requested_at | applied_at | seconds_to_apply |
|---|---|---|---|---|---|---|---|---|
| 1 | inject_fault | PLT-E-A03 | overheating | sascha.vetter@databricks.com | applied | 2026-10-06 17:12:38.582498+00:00 | 2026-10-06 17:12:39.001621+00:00 | 0.42 |
| 2 | repair | PLT-E-A03 |  | sascha.vetter@databricks.com | applied | 2026-10-06 17:17:43.295412+00:00 | 2026-10-06 17:17:45.001512+00:00 | 1.71 |

Output:

| work_order_id | station_id | plant_id | line_id | priority | status | failure_probability | risk_band | top_signal | description | assigned_technician_id | created_by | created_at | updated_at | completed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLT-E-A03 | PLT-E | PLT-E-A | P1 | completed | 0.7868 | HIGH | motor_current_a | E2E test: overheating alert |  | sascha.vetter@databricks.com | 2026-10-06T17:16:25.838Z | 2026-10-06T17:17:43.289Z | 2026-10-06T17:17:43.289Z |

Output:

| Status | work_orders | avg_minutes_to_complete |
|---|---|---|
| completed | 1 | 1.3000000000 |
