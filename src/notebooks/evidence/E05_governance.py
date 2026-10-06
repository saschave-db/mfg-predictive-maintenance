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
# MAGIC **What this notebook proves.** Each control as recorded in Unity Catalog, plus the effect of masking, and metric
# MAGIC views answering KPI queries.

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
