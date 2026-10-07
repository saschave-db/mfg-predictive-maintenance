# Executed notebook: E00_overview

Exported from Databricks job run `994447175034582` (task `E00_overview`, task run `389548815414273`).

Result: **SUCCESS** · start 2026-10-07T22:56:13.297000+00:00 · end 2026-10-07T22:56:54.102000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


# E00 · Evidence overview: live predictive maintenance on Databricks

This notebook set proves, step by step, that the demo was built and runs on this workspace.
Every output below is produced live by querying the workspace (SDK calls, SQL on Unity Catalog, SQL on Lakebase).
All data is synthetic.

```
Simulator (96 stations, 1 Hz) --Zerobus--> pdm_raw.sensor_readings (Delta)
  --SDP continuous--> sensor_readings_clean -> station_risk_scores (windows + UC model in-stream) -> station_health_current
  --Lakebase continuous sync--> pdm_live.station_risk_scores (Postgres) --> Databricks App
App --> Lakebase pdm_ops.work_orders / sim_commands --Lakehouse Sync--> UC pdm_ops.lb_*_history
Metric views pdm_ops.*_metrics --> Genie agent;  UC model --> Model Serving pdm-station-risk --> App what-if
```

| Step | Notebook | What it proves |
|---|---|---|
| Data generation + ingestion | E01 | Zerobus writes from the gateway service principal land in a governed Delta table |
| ETL | E02 | Continuous SDP pipeline, expectations, freshness, lineage |
| ML | E03 | Registered model, metrics, in-stream scores reproducible with the registry and Model Serving |
| Lakebase | E04 | OLTP tables, synced table, freshness Delta vs Postgres, Lakehouse Sync back to UC |
| Governance | E05 | Grants, masks, row filter, tags, metric views; enforcement proven on the app's service principal (non-owner) |
| Genie | E06 | Agent configuration and live answers checked against reference SQL |
| App | E07 | App deployment, resources, and its writes to Lakebase |
| End to end | E08 | Live fault injected and traced to a HIGH alert, work order, repair, recovery |
| Source integrity | E09 | Deployed files are byte-identical to the committed source (SHA-256), full pipeline source printed |

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
print("evidence run at (UTC):", datetime.datetime.now(datetime.timezone.utc).isoformat())
print("workspace:", w.config.host)
print("run as:", w.current_user.me().user_name)
```

Output:

```text
evidence run at (UTC): 2026-10-07T22:56:35.799923+00:00
workspace: https://fevm-serverless-stable-am1uc2.cloud.databricks.com
run as: sascha.vetter@databricks.com
```

## State of every deployed resource
One line per resource, read from the workspace APIs at run time.

```python
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
```

Output:

| resource | name | status |
|---|---|---|
| SDP pipeline | pdm_live_pipeline | state=RUNNING, continuous=True, serverless=True |
| Job | pdm_evidence_notebooks | job_id=755461157363253, last run=RUNNING |
| Job | pdm_04_live_evidence | job_id=565657892038932, last run=SUCCESS |
| Job | pdm_02_train_model | job_id=269340780177784, last run=SUCCESS |
| Job | pdm_01_backfill_history | job_id=327188914455836, last run=SUCCESS |
| Job | pdm_simulator_zerobus | job_id=16077621483238, last run=RUNNING |
| Job | pdm_03_governance_semantic | job_id=438031727317059, last run=SUCCESS |
| Job | pdm_00_setup_uc | job_id=395785416821222, last run=SUCCESS |
| Model Serving | pdm-station-risk | ready=READY, served=[('station_failure_model', '2')] |
| Databricks App | pdm-plant-health-live | app=RUNNING, compute=ACTIVE, url=https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com |
| Lakebase endpoint | projects/pdm-demo/branches/production/endpoints/primary | state=ACTIVE |
| Lakebase synced table | serverless_stable_am1uc2_catalog.pdm_live.station_risk_scores | state=SYNCED_TABLE_ONLINE_CONTINUOUS_UPDATE |
| Genie agent | Plant Maintenance Agent | space_id=01f1c10d662111078cd7326dff1774c6 |

## Unity Catalog objects of the demo

```python
display(spark.sql(f"""
SELECT table_schema, table_name, table_type, comment
FROM {CATALOG}.information_schema.tables
WHERE table_schema LIKE 'pdm_%' AND NOT startswith(table_name, '__') AND NOT startswith(table_name, 'event_log_')
ORDER BY table_schema, table_name"""))
```

Output:

| table_schema | table_name | table_type | comment |
|---|---|---|---|
