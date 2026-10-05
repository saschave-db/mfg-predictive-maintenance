# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Unity Catalog setup
# MAGIC Creates the schemas, the Zerobus landing table, synthetic reference data, and least-privilege grants
# MAGIC for the Zerobus producer service principal. All data is synthetic.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("zerobus_sp_app_id", "240a5501-f956-4282-a2a7-ccc7614683a7")
CATALOG = dbutils.widgets.get("catalog")
SP = dbutils.widgets.get("zerobus_sp_app_id")

import os, sys
sys.path.append(os.path.abspath(".."))
from pdm.config import SCHEMA_RAW, SCHEMA_CORE, SCHEMA_ML, SCHEMA_OPS, SENSORS
from pdm.physics import build_station_master

# COMMAND ----------

schemas = {
    SCHEMA_RAW: "Landing zone: Zerobus telemetry and reference data (synthetic).",
    SCHEMA_CORE: "SDP output: cleaned telemetry, window features, live risk scores.",
    SCHEMA_ML: "Training sets and the station failure model.",
    SCHEMA_OPS: "Operational tables (work orders) and governed metric views.",
}
for s, c in schemas.items():
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{s} COMMENT '{c}'")
display(spark.sql(f"SHOW SCHEMAS IN {CATALOG} LIKE 'pdm_*'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Zerobus target table
# MAGIC Zerobus writes into a pre-created **managed Delta** table. It never creates or alters tables.

# COMMAND ----------

sensor_cols = ",\n  ".join(f"{s} DOUBLE" for s in SENSORS)
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA_RAW}.sensor_readings (
  event_id STRING COMMENT 'Deterministic id (station + seq); used for de-duplication (Zerobus is at-least-once)',
  gateway_id STRING COMMENT 'Plant edge gateway that pushed the record',
  plant_id STRING,
  line_id STRING,
  station_id STRING,
  ts TIMESTAMP COMMENT 'Sensor sample time (UTC)',
  seq BIGINT COMMENT 'Per-station sequence number',
  {sensor_cols},
  firmware STRING
)
COMMENT 'Raw 1 Hz station telemetry pushed by plant gateways via Lakeflow Connect Zerobus Ingest (synthetic).'
""")
display(spark.sql(f"DESCRIBE TABLE {CATALOG}.{SCHEMA_RAW}.sensor_readings"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference data: stations and technicians

# COMMAND ----------

stations = spark.createDataFrame(build_station_master())
(stations.write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{CATALOG}.{SCHEMA_RAW}.station_master"))
spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA_RAW}.station_master IS "
          "'Station master data: 3 plants x 4 lines x 8 stations, with nominal sensor operating points (synthetic).'")
display(spark.sql(f"""
SELECT plant_name, station_type, count(*) AS stations
FROM {CATALOG}.{SCHEMA_RAW}.station_master GROUP BY ALL ORDER BY ALL"""))

# COMMAND ----------

import random
random.seed(11)
first = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Drew", "Avery", "Quinn", "Reese"]
last = ["Novak", "Okafor", "Lindqvist", "Moreau", "Tanaka", "Silva", "Kowalski", "Haddad", "Brennan", "Iyer"]
techs = []
for i, plant in enumerate(["PLT-N", "PLT-S", "PLT-E"] * 6):
    fn, ln = random.choice(first), random.choice(last)
    techs.append(dict(
        technician_id=f"T{i+1:03d}", full_name=f"{fn} {ln}", home_plant_id=plant,
        skill=random.choice(["mechanical", "electrical", "hydraulics"]),
        email=f"{fn.lower()}.{ln.lower()}{i}@example-mfg.test", phone=f"+1-555-01{i:02d}",
    ))
(spark.createDataFrame(techs).write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{CATALOG}.{SCHEMA_RAW}.technicians"))
spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA_RAW}.technicians IS "
          "'Maintenance technicians (synthetic). email/phone are PII and masked for non-supervisors.'")
display(spark.table(f"{CATALOG}.{SCHEMA_RAW}.technicians").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Least-privilege grants for the Zerobus producer
# MAGIC Zerobus needs explicit **table-level** `MODIFY` + `SELECT`; schema inheritance is not enough.

# COMMAND ----------

for stmt in [
    f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{SP}`",
    f"GRANT USE SCHEMA ON SCHEMA {CATALOG}.{SCHEMA_RAW} TO `{SP}`",
    f"GRANT MODIFY, SELECT ON TABLE {CATALOG}.{SCHEMA_RAW}.sensor_readings TO `{SP}`",
]:
    spark.sql(stmt)
    print("OK:", stmt)
display(spark.sql(f"SHOW GRANTS `{SP}` ON TABLE {CATALOG}.{SCHEMA_RAW}.sensor_readings"))
