# Databricks notebook source
# MAGIC %md
# MAGIC # E05 · Unity Catalog governance and the semantic layer
# MAGIC
# MAGIC **What was built** (notebook `03_governance_semantic`):
# MAGIC * Least-privilege grants: Zerobus SP (write bronze only), app SP (read gold + metric views).
# MAGIC * PII column masks on technician `email` / `phone` (`pdm_ops.mask_pii`), plant row filter (`pdm_ops.plant_row_filter`).
# MAGIC * Tags on schemas, tables and PII columns (`pdm_` keys; the workspace enforces governed policies on `domain`, `source`, `pii`).
# MAGIC * Metric views `maintenance_metrics`, `station_risk_metrics`, `work_order_metrics` with synonyms for Genie.
# MAGIC * The model is a UC securable (`pdm_ml.station_failure_model`) with alias `@champion`.
# MAGIC
# MAGIC **What this notebook proves.** Each control as recorded in Unity Catalog, and that the row filter and masks are
# MAGIC **enforced on a non-owner identity**: the app's service principal. Owners are often exempt, so the owner's view alone
# MAGIC proves little. Section 2b shows the SP's own queries (from query history) and what Unity Catalog returned to it.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
spark.sql(f"USE CATALOG {CATALOG}")
APP_SP = w.apps.get(APP_NAME).service_principal_client_id

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Grants for the two service principals

# COMMAND ----------

display(spark.sql(f"SHOW GRANTS `{ZEROBUS_SP}` ON TABLE pdm_raw.sensor_readings"))
for obj in ["SCHEMA pdm_core", "SCHEMA pdm_ops", "TABLE pdm_raw.station_master"]:
    display(spark.sql(f"SHOW GRANTS `{APP_SP}` ON {obj}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Column masks and row filter

# COMMAND ----------

display(spark.sql(f"""SELECT table_schema, table_name, column_name, mask_name FROM {CATALOG}.information_schema.column_masks
                      WHERE table_schema LIKE 'pdm_%'"""))
display(spark.sql(f"""SELECT table_schema, table_name, filter_name, target_columns FROM {CATALOG}.information_schema.row_filters
                      WHERE table_schema LIKE 'pdm_%'"""))
print("Effect for the current user (owner: exempt from row filter, not in pdm_supervisors):")
display(spark.sql("SELECT technician_id, full_name, home_plant_id, email, phone FROM pdm_raw.technicians ORDER BY technician_id LIMIT 6"))
print("Function bodies:")
for f in ["pdm_ops.mask_pii", "pdm_ops.plant_row_filter"]:
    print(spark.sql(f"DESCRIBE FUNCTION EXTENDED {f}").filter("function_desc LIKE 'Body:%' OR function_desc LIKE 'Function:%'").toPandas().to_string(index=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2b · Enforcement on a non-owner identity: the app's service principal
# MAGIC The app endpoint `/api/governance/technicians` runs `SELECT current_user(), ... FROM pdm_raw.technicians` on the SQL
# MAGIC warehouse **as the app SP**. The SP has `SELECT` on the table, is granted only `PLT-N` in `pdm_ops.plant_access`, and is
# MAGIC not in `pdm_supervisors`. Expected: 6 of 18 technicians (Plant North only), email and phone redacted.
# MAGIC The raw HTTP response of that call is in `evidence/08_app/governance_as_app_sp.json`.

# COMMAND ----------

display(spark.sql("SELECT * FROM pdm_ops.plant_access"))
print("Row filter function as deployed:")
print(spark.sql("DESCRIBE FUNCTION EXTENDED pdm_ops.plant_row_filter").filter("function_desc LIKE 'Body:%'").first()[0])
print("\nOwner view for contrast (owner is exempt from the filter, masks still apply because the owner is not a supervisor):")
display(spark.sql("SELECT home_plant_id, count(*) AS technicians FROM pdm_raw.technicians GROUP BY ALL ORDER BY 1"))

# COMMAND ----------

from databricks.sdk.service.sql import QueryFilter
sp_user = next(w.service_principals.list(filter=f"applicationId eq {APP_SP}"))
print("app service principal:", sp_user.display_name, "| application id:", APP_SP, "| user id:", sp_user.id)
resp = w.query_history.list(filter_by=QueryFilter(user_ids=[int(sp_user.id)]), include_metrics=True, max_results=50)
hist = list(getattr(resp, "res", None) or ([] if hasattr(resp, "res") else resp))
tech = [q for q in hist if "pdm_raw.technicians" in (q.query_text or "")]
print(f"{len(tech)} technician queries executed by the app SP (Query History API):")
for q in tech[:5]:
    print(f"- query_id={q.query_id} status={q.status.value} executed_as={q.executed_as_user_name} "
          f"rows_produced={q.metrics.rows_produced_count if q.metrics else None} start={q.query_start_time_ms}")
    print("  ", q.query_text[:160])

# COMMAND ----------

# Same facts from the audit system table (system tables can lag a few minutes behind).
display(spark.sql(f"""
SELECT statement_id, executed_by, executed_as, execution_status, produced_rows, start_time, left(statement_text, 120) AS statement
FROM system.query.history
WHERE executed_by_user_id = '{sp_user.id}' AND statement_text LIKE '%pdm_raw.technicians%'
ORDER BY start_time DESC LIMIT 5"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Tags

# COMMAND ----------

display(spark.sql(f"SELECT schema_name, tag_name, tag_value FROM {CATALOG}.information_schema.schema_tags WHERE schema_name LIKE 'pdm_%' ORDER BY 1, 2"))
display(spark.sql(f"SELECT schema_name, table_name, tag_name, tag_value FROM {CATALOG}.information_schema.table_tags WHERE schema_name LIKE 'pdm_%'"))
display(spark.sql(f"SELECT schema_name, table_name, column_name, tag_name, tag_value FROM {CATALOG}.information_schema.column_tags WHERE schema_name LIKE 'pdm_%'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Metric views: definitions and KPI queries

# COMMAND ----------

for mv in ["maintenance_metrics", "station_risk_metrics", "work_order_metrics"]:
    print(f"===== pdm_ops.{mv}")
    print(spark.sql(f"SHOW CREATE TABLE pdm_ops.{mv}").first()[0])

# COMMAND ----------

display(spark.sql("""SELECT Plant, MEASURE(Failures) AS failures, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min,
                     MEASURE(`Preventive Share`) AS preventive_share, MEASURE(`Parts Cost USD`) AS parts_cost_usd
                     FROM pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY Plant"""))
display(spark.sql("""SELECT Plant, MEASURE(`Stations At High Risk`) AS high_risk_stations, MEASURE(`Avg Failure Probability`) AS avg_risk,
                     MEASURE(`Avg Sensor To Score Latency Seconds`) AS latency_s
                     FROM pdm_ops.station_risk_metrics WHERE `Score Time` > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY Plant"""))
display(spark.sql("""SELECT Status, Priority, MEASURE(`Work Orders`) AS work_orders, MEASURE(`Avg Risk At Creation`) AS avg_risk_at_creation
                     FROM pdm_ops.work_order_metrics GROUP BY ALL"""))
