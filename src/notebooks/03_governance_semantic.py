# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Governance and semantic layer
# MAGIC * **Work orders from Lakebase:** Lakehouse Sync streams Postgres changes into `pdm_ops.lb_work_orders_history` (SCD2 CDC).
# MAGIC   A view exposes the current state of each work order.
# MAGIC * **Metric views:** governed KPI definitions shared by Genie, dashboards and SQL.
# MAGIC * **Fine-grained access:** PII column masks and a plant-level row filter on technicians, plus tags.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("app_sp", "2a9b01a6-1050-4c7d-b389-45351bf8e97b")
CATALOG = dbutils.widgets.get("catalog")
APP_SP = dbutils.widgets.get("app_sp")  # the app's service principal: the non-owner identity used to prove enforcement
OWNER = spark.sql("SELECT current_user()").first()[0]
spark.sql(f"USE CATALOG {CATALOG}")


def run(sql):
    try:
        spark.sql(sql)
        print("OK  ", " ".join(sql.split())[:150])
    except Exception as e:
        print("FAIL", " ".join(sql.split())[:150], "->", str(e).splitlines()[0][:200])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Current work orders (from Lakebase via Lakehouse Sync)

# COMMAND ----------

run("""
CREATE OR REPLACE VIEW pdm_ops.work_orders_current
COMMENT 'Current state of maintenance work orders created in the Plant Health Live app (Lakebase -> Lakehouse Sync).'
AS SELECT work_order_id, station_id, plant_id, line_id, priority, status, failure_probability, risk_band, top_signal,
          description, assigned_technician_id, created_by, created_at, updated_at, completed_at
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY work_order_id ORDER BY _pg_lsn DESC) AS rn
  FROM pdm_ops.lb_work_orders_history
  WHERE _pg_change_type IN ('insert', 'update_postimage', 'delete')
) WHERE rn = 1 AND _pg_change_type != 'delete'
""")
display(spark.sql("SELECT status, count(*) AS work_orders FROM pdm_ops.work_orders_current GROUP BY ALL"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metric views

# COMMAND ----------

run(f"""
CREATE OR REPLACE VIEW pdm_ops.maintenance_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
source: {CATALOG}.pdm_core.maintenance_events
comment: "Reliability KPIs from the maintenance log: failures, repairs, downtime, cost. Time is compressed (1 demo minute ~ 1 operating hour)."
dimensions:
  - name: Plant
    expr: plant_name
    synonyms: [site, factory]
  - name: Line
    expr: line_id
    synonyms: [production line]
  - name: Station
    expr: station_id
    synonyms: [machine, asset, equipment]
  - name: Station Type
    expr: station_type
    synonyms: [machine type, asset class]
  - name: Criticality
    expr: criticality
  - name: Event Type
    expr: event_type
    comment: "failure, corrective_repair or preventive_repair"
  - name: Failure Mode
    expr: failure_mode
    synonyms: [root cause, fault type]
  - name: Event Date
    expr: event_date
  - name: Event Hour
    expr: "DATE_TRUNC('HOUR', event_ts)"
measures:
  - name: Failures
    expr: COUNT(1) FILTER (WHERE event_type = 'failure')
    synonyms: [breakdowns, unplanned stops]
  - name: Corrective Repairs
    expr: COUNT(1) FILTER (WHERE event_type = 'corrective_repair')
  - name: Preventive Repairs
    expr: COUNT(1) FILTER (WHERE event_type = 'preventive_repair')
    synonyms: [planned maintenance]
  - name: Downtime Minutes
    expr: SUM(downtime_min)
    format: {{type: number, decimal_places: {{type: exact, places: 0}}}}
  - name: Parts Cost USD
    expr: SUM(parts_cost_usd)
    format: {{type: currency, currency_code: USD}}
  - name: Mean Time To Repair Minutes
    expr: AVG(downtime_min) FILTER (WHERE event_type = 'corrective_repair')
    synonyms: [MTTR]
  - name: Preventive Share
    expr: "COUNT(1) FILTER (WHERE event_type = 'preventive_repair') * 1.0 / NULLIF(COUNT(1) FILTER (WHERE event_type IN ('preventive_repair', 'corrective_repair')), 0)"
    format: {{type: percentage}}
  - name: Stations With Failures
    expr: COUNT(DISTINCT station_id) FILTER (WHERE event_type = 'failure')
$$
""")

run(f"""
CREATE OR REPLACE VIEW pdm_ops.station_risk_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
source: {CATALOG}.pdm_core.station_risk_scores
comment: "Live predicted failure risk per station, scored every 10 s by the SDP pipeline with the UC model @champion."
joins:
  - name: dim_station
    source: {CATALOG}.pdm_raw.station_master
    'on': source.station_id = dim_station.station_id
dimensions:
  - name: Plant
    expr: dim_station.plant_name
    synonyms: [site, factory]
  - name: Line
    expr: source.line_id
  - name: Station
    expr: source.station_id
    synonyms: [machine, asset]
  - name: Station Type
    expr: source.station_type
  - name: Criticality
    expr: source.criticality
  - name: Risk Band
    expr: source.risk_band
    comment: "NORMAL (<40%), ELEVATED (40-70%), HIGH (>=70%), DOWN (stopped)"
  - name: Top Signal
    expr: source.top_signal
    synonyms: [driver, main contributor, anomalous sensor]
  - name: Score Minute
    expr: "DATE_TRUNC('MINUTE', source.window_end)"
  - name: Score Time
    expr: source.window_end
measures:
  - name: Avg Failure Probability
    expr: AVG(source.failure_probability)
    format: {{type: percentage}}
    synonyms: [risk, maintenance probability]
  - name: Max Failure Probability
    expr: MAX(source.failure_probability)
    format: {{type: percentage}}
  - name: Scored Windows
    expr: COUNT(1)
  - name: High Risk Windows
    expr: COUNT(1) FILTER (WHERE source.risk_band = 'HIGH')
  - name: Stations At High Risk
    expr: COUNT(DISTINCT source.station_id) FILTER (WHERE source.risk_band = 'HIGH')
  - name: Stations Down
    expr: COUNT(DISTINCT source.station_id) FILTER (WHERE source.risk_band = 'DOWN')
  - name: Latest Score Time
    expr: MAX(source.window_end)
  - name: Avg Sensor To Score Latency Seconds
    expr: AVG(unix_millis(source.scored_at) - unix_millis(source.last_reading_ts)) / 1000.0
    comment: "Seconds from the newest sensor reading in a window to its risk score being written."
    synonyms: [pipeline latency, freshness]
$$
""")

run(f"""
CREATE OR REPLACE VIEW pdm_ops.work_order_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
source: {CATALOG}.pdm_ops.work_orders_current
comment: "Maintenance work orders raised from live risk alerts in the Plant Health Live app."
joins:
  - name: dim_station
    source: {CATALOG}.pdm_raw.station_master
    'on': source.station_id = dim_station.station_id
dimensions:
  - name: Plant
    expr: dim_station.plant_name
  - name: Line
    expr: source.line_id
  - name: Station
    expr: source.station_id
  - name: Station Type
    expr: dim_station.station_type
  - name: Priority
    expr: source.priority
  - name: Status
    expr: source.status
  - name: Risk Band At Creation
    expr: source.risk_band
  - name: Top Signal At Creation
    expr: source.top_signal
  - name: Created Date
    expr: "CAST(source.created_at AS DATE)"
measures:
  - name: Work Orders
    expr: COUNT(1)
    synonyms: [tickets, maintenance orders]
  - name: Open Work Orders
    expr: COUNT(1) FILTER (WHERE source.status IN ('open', 'in_progress'))
    synonyms: [backlog]
  - name: Completed Work Orders
    expr: COUNT(1) FILTER (WHERE source.status = 'completed')
  - name: Avg Risk At Creation
    expr: AVG(source.failure_probability)
    format: {{type: percentage}}
  - name: Avg Minutes To Complete
    expr: AVG((unix_seconds(source.completed_at) - unix_seconds(source.created_at)) / 60.0) FILTER (WHERE source.status = 'completed')
$$
""")
display(spark.sql("SHOW VIEWS IN pdm_ops"))

# COMMAND ----------

display(spark.sql("""
SELECT `Station Type`, MEASURE(Failures) AS failures, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min,
       MEASURE(`Preventive Share`) AS preventive_share, MEASURE(`Parts Cost USD`) AS parts_cost_usd
FROM pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY failures DESC"""))

# COMMAND ----------

display(spark.sql("""
SELECT Plant, MEASURE(`Stations At High Risk`) AS high_risk_stations, MEASURE(`Avg Failure Probability`) AS avg_risk,
       MEASURE(`Avg Sensor To Score Latency Seconds`) AS latency_s, MEASURE(`Latest Score Time`) AS latest
FROM pdm_ops.station_risk_metrics WHERE `Score Time` > current_timestamp() - INTERVAL 10 MINUTES
GROUP BY ALL ORDER BY Plant"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Fine-grained access control and tags
# MAGIC * `email` / `phone` are masked unless the reader is in `pdm_supervisors`.
# MAGIC * Tag keys are `pdm_`-prefixed: this workspace enforces governed tag policies on `domain`, `source` and `pii`.
# MAGIC * Technicians are filtered by `pdm_ops.plant_access` (principal -> plant). The app's service principal is granted
# MAGIC   Plant North only and is not a supervisor, so it is the non-owner identity used to prove enforcement (see E05).

# COMMAND ----------

run("""CREATE OR REPLACE FUNCTION pdm_ops.mask_pii(v STRING) RETURNS STRING
       COMMENT 'Reveal PII only to members of pdm_supervisors'
       RETURN CASE WHEN is_account_group_member('pdm_supervisors') THEN v ELSE '***redacted***' END""")
# Principal -> plant mapping drives row-level security (no account-group changes needed).
run("""CREATE TABLE IF NOT EXISTS pdm_ops.plant_access (principal STRING NOT NULL, plant_id STRING NOT NULL,
       granted_at TIMESTAMP) COMMENT 'Row-level security mapping: which principal may see which plant'""")
run(f"DELETE FROM pdm_ops.plant_access WHERE principal = '{APP_SP}'")
run(f"INSERT INTO pdm_ops.plant_access VALUES ('{APP_SP}', 'PLT-N', current_timestamp())")
run(f"""CREATE OR REPLACE FUNCTION pdm_ops.plant_row_filter(p_plant STRING) RETURNS BOOLEAN
       COMMENT 'Owner and pdm_all_plants see everything; other principals only plants granted in pdm_ops.plant_access'
       RETURN current_user() = '{OWNER}' OR is_account_group_member('pdm_all_plants')
              OR EXISTS (SELECT 1 FROM pdm_ops.plant_access a WHERE a.principal = current_user() AND a.plant_id = p_plant)""")
# The app SP may query the table; the row filter and masks decide what it actually sees.
run(f"GRANT SELECT ON TABLE pdm_raw.technicians TO `{APP_SP}`")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET MASK pdm_ops.mask_pii")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET MASK pdm_ops.mask_pii")
run("ALTER TABLE pdm_raw.technicians SET ROW FILTER pdm_ops.plant_row_filter ON (home_plant_id)")

for schema in ["pdm_raw", "pdm_core", "pdm_ml", "pdm_ops"]:
    run(f"ALTER SCHEMA {schema} SET TAGS ('pdm_domain' = 'manufacturing', 'pdm_use_case' = 'predictive_maintenance', 'pdm_data_class' = 'synthetic')")
run("ALTER TABLE pdm_raw.sensor_readings SET TAGS ('pdm_source' = 'zerobus', 'pdm_latency_tier' = 'realtime')")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET TAGS ('pdm_pii' = 'email')")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET TAGS ('pdm_pii' = 'phone')")

# COMMAND ----------

# The owner is exempt from the row filter but not in pdm_supervisors, so rows are visible and PII is masked.
display(spark.sql("SELECT technician_id, full_name, home_plant_id, email, phone FROM pdm_raw.technicians ORDER BY technician_id LIMIT 6"))
display(spark.sql(f"""SELECT tag_name, tag_value, count(*) AS objects FROM {CATALOG}.information_schema.schema_tags
                      WHERE schema_name LIKE 'pdm_%' GROUP BY ALL"""))
