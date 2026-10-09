# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Industry context: Tier-1 EV battery enclosure supplier
# MAGIC
# MAGIC Volta Industrial (fictional) makes aluminum battery enclosures for EV OEMs. Each of its 12 lines builds one
# MAGIC part family for one OEM vehicle program and ships **just-in-sequence (JIS)**. If a station fails for longer than the
# MAGIC JIS buffer, the OEM's assembly line stops and the supplier is charged for every minute.
# MAGIC
# MAGIC This notebook adds that context to the governed data, so risk is expressed in the supplier's own terms:
# MAGIC * `pdm_raw.line_programs`: OEM customer, vehicle program, part family, JIS buffer and contract line-stop charge per line.
# MAGIC * `pdm_raw.process_steps`: the enclosure process step and critical quality characteristic behind each station position.
# MAGIC * `pdm_ops.oem_delivery_exposure`: per line, live risk joined to the OEM contract. It answers "if the riskiest station
# MAGIC   fails now, does the OEM line stop, and what does it cost us?"
# MAGIC
# MAGIC All OEMs, programs and contract terms are synthetic.

# COMMAND ----------

dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("app_sp", "2a9b01a6-1050-4c7d-b389-45351bf8e97b")
CATALOG = dbutils.widgets.get("catalog")
APP_SP = dbutils.widgets.get("app_sp")
spark.sql(f"USE CATALOG {CATALOG}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## OEM programs per line (synthetic contract terms)

# COMMAND ----------

# line_id, oem_customer, vehicle_program, part_family, jis_buffer_min, line_stop_charge_usd_per_min, enclosures_per_hour
PROGRAMS = [
    ("PLT-N-A", "Nordvik Motors", "NV-e7 SUV", "Battery tray (lower housing)", 60, 15000, 42),
    ("PLT-N-B", "Nordvik Motors", "NV-e7 SUV", "Battery cover (upper housing)", 75, 15000, 42),
    ("PLT-N-C", "Nordvik Motors", "NV-e5 Crossover", "Battery tray (lower housing)", 60, 12000, 36),
    ("PLT-N-D", "Fjord Electric", "FE Pace Sedan", "Cooling plate assembly", 90, 9000, 48),
    ("PLT-S-A", "Fjord Electric", "FE Pace Sedan", "Battery tray (lower housing)", 45, 18000, 40),
    ("PLT-S-B", "Fjord Electric", "FE Pace Sedan", "Battery cover (upper housing)", 60, 18000, 40),
    ("PLT-S-C", "Fjord Electric", "FE Haul Van", "Battery tray (lower housing)", 75, 10000, 30),
    ("PLT-S-D", "Aurora Elbil", "Aurora A3 Hatch", "Cooling plate assembly", 90, 8000, 50),
    ("PLT-E-A", "Aurora Elbil", "Aurora A3 Hatch", "Battery tray (lower housing)", 60, 11000, 45),
    ("PLT-E-B", "Aurora Elbil", "Aurora A3 Hatch", "Battery cover (upper housing)", 75, 11000, 45),
    ("PLT-E-C", "Aurora Elbil", "Aurora X5 SUV", "Battery tray (lower housing)", 45, 16000, 34),
    ("PLT-E-D", "Nordvik Motors", "NV-e5 Crossover", "Cooling plate assembly", 90, 9000, 48),
]
spark.createDataFrame(PROGRAMS, "line_id string, oem_customer string, vehicle_program string, part_family string, "
                      "jis_buffer_min int, line_stop_charge_usd_per_min int, enclosures_per_hour int") \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pdm_raw.line_programs")
spark.sql("COMMENT ON TABLE pdm_raw.line_programs IS 'OEM vehicle program supplied by each line, with just-in-sequence "
          "buffer and contract line-stop charge (synthetic).'")
display(spark.table("pdm_raw.line_programs").orderBy("line_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enclosure process step per station position
# MAGIC Every line has the same 8-station flow. The station types in the simulator map to these steps.

# COMMAND ----------

STEPS = [
    (1, "press", "Stamping of tray floor and side members", "Dimensional accuracy of formed parts"),
    (2, "cnc_mill", "Machining of extrusion profiles", "Hole position for module mounting"),
    (3, "welder", "Friction-stir welding of frame", "Weld seam integrity (crash load path)"),
    (4, "robot_arm", "Sealant dispensing and handling", "Bead continuity (IP67 sealing)"),
    (5, "conveyor", "Transfer to leak test", "Takt and part sequence"),
    (6, "cnc_mill", "Flatness machining of cooling interface", "Flatness of thermal interface"),
    (7, "welder", "Laser welding of cover brackets", "Weld penetration"),
    (8, "press", "Clinching and end-of-line press", "Joint strength before JIS shipment"),
]
spark.createDataFrame(STEPS, "station_position int, station_type string, process_step string, "
                      "critical_quality_characteristic string") \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("pdm_raw.process_steps")
spark.sql("COMMENT ON TABLE pdm_raw.process_steps IS 'Battery enclosure process step and critical quality "
          "characteristic per station position on every line (synthetic).'")
display(spark.table("pdm_raw.process_steps"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## OEM delivery exposure per line (live)
# MAGIC * `typical_unplanned_downtime_min`: average corrective-repair downtime for the riskiest station's type, from the maintenance log.
# MAGIC * `oem_line_stop_min_if_fails`: downtime beyond the JIS buffer. This is how long the OEM's line would stand still.
# MAGIC * `exposure_usd_if_fails`: those minutes times the contract line-stop charge.

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW pdm_ops.oem_delivery_exposure
COMMENT 'Per line: live failure risk joined to the OEM JIS contract. Shows whether a failure of the riskiest station would stop the OEM line and the contract charge (synthetic).'
AS
WITH ranked AS (
  SELECT h.*, CAST(right(h.station_id, 2) AS INT) AS station_position,
         ROW_NUMBER() OVER (PARTITION BY h.line_id ORDER BY h.failure_probability DESC) AS rn
  FROM pdm_core.station_health_current h
),
downtime AS (
  SELECT station_type, AVG(downtime_min) AS typical_unplanned_downtime_min
  FROM pdm_core.maintenance_events WHERE event_type = 'corrective_repair' GROUP BY station_type
),
line_risk AS (
  SELECT line_id, COUNT_IF(risk_band = 'HIGH') AS high_risk_stations,
         COUNT_IF(risk_band = 'ELEVATED') AS elevated_risk_stations
  FROM pdm_core.station_health_current GROUP BY line_id
)
SELECT p.line_id, r.plant_id, p.oem_customer, p.vehicle_program, p.part_family,
       r.station_id AS riskiest_station_id, s.process_step AS riskiest_process_step,
       s.critical_quality_characteristic, r.risk_band AS riskiest_risk_band,
       ROUND(r.failure_probability, 4) AS riskiest_failure_probability, r.top_signal,
       l.high_risk_stations, l.elevated_risk_stations,
       p.jis_buffer_min, ROUND(d.typical_unplanned_downtime_min, 0) AS typical_unplanned_downtime_min,
       ROUND(GREATEST(0, d.typical_unplanned_downtime_min - p.jis_buffer_min), 0) AS oem_line_stop_min_if_fails,
       p.line_stop_charge_usd_per_min,
       ROUND(GREATEST(0, d.typical_unplanned_downtime_min - p.jis_buffer_min) * p.line_stop_charge_usd_per_min, 0)
         AS exposure_usd_if_fails,
       ROUND(r.failure_probability * GREATEST(0, d.typical_unplanned_downtime_min - p.jis_buffer_min)
             * p.line_stop_charge_usd_per_min, 0) AS risk_weighted_exposure_usd
FROM pdm_raw.line_programs p
JOIN ranked r ON r.line_id = p.line_id AND r.rn = 1
JOIN pdm_raw.process_steps s ON s.station_position = r.station_position
JOIN downtime d ON d.station_type = r.station_type
JOIN line_risk l ON l.line_id = p.line_id
""")
for t in ("pdm_raw.line_programs", "pdm_raw.process_steps"):
    spark.sql(f"ALTER TABLE {t} SET TAGS ('pdm_domain' = 'manufacturing', 'pdm_data_class' = 'synthetic')")
for obj in ("TABLE pdm_raw.line_programs", "TABLE pdm_raw.process_steps", "TABLE pdm_ops.oem_delivery_exposure"):
    spark.sql(f"GRANT SELECT ON {obj} TO `{APP_SP}`")
    print("granted SELECT on", obj, "to app SP", APP_SP)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exposure right now, riskiest lines first

# COMMAND ----------

display(spark.sql("""
SELECT line_id, oem_customer, vehicle_program, riskiest_station_id, riskiest_process_step, riskiest_risk_band,
       ROUND(riskiest_failure_probability * 100, 1) AS risk_pct, jis_buffer_min, typical_unplanned_downtime_min,
       oem_line_stop_min_if_fails, exposure_usd_if_fails, risk_weighted_exposure_usd
FROM pdm_ops.oem_delivery_exposure ORDER BY risk_weighted_exposure_usd DESC, line_id"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Exposure per OEM customer
# MAGIC The supplier scorecard is kept per OEM. This is the view a COO takes into the customer review.

# COMMAND ----------

display(spark.sql("""
SELECT oem_customer, COUNT(*) AS lines, SUM(high_risk_stations) AS high_risk_stations,
       SUM(exposure_usd_if_fails) AS exposure_usd_if_riskiest_fail, SUM(risk_weighted_exposure_usd) AS risk_weighted_exposure_usd
FROM pdm_ops.oem_delivery_exposure GROUP BY ALL ORDER BY risk_weighted_exposure_usd DESC"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Contract exposure of one unplanned failure, per line (independent of the current risk)
# MAGIC Uses the fleet-average corrective downtime. This feeds the value model in `presentation/deck.md`.

# COMMAND ----------

display(spark.sql("""
WITH avg_dt AS (SELECT AVG(downtime_min) AS dt FROM pdm_core.maintenance_events WHERE event_type = 'corrective_repair')
SELECT p.line_id, p.oem_customer, p.vehicle_program, p.jis_buffer_min, ROUND(a.dt, 0) AS avg_unplanned_downtime_min,
       ROUND(GREATEST(0, a.dt - p.jis_buffer_min), 0) AS oem_line_stop_min,
       ROUND(GREATEST(0, a.dt - p.jis_buffer_min) * p.line_stop_charge_usd_per_min, 0) AS charge_usd_per_failure
FROM pdm_raw.line_programs p CROSS JOIN avg_dt a ORDER BY p.line_id"""))
display(spark.sql("""
WITH avg_dt AS (SELECT AVG(downtime_min) AS dt FROM pdm_core.maintenance_events WHERE event_type = 'corrective_repair')
SELECT ROUND(AVG(GREATEST(0, a.dt - p.jis_buffer_min)), 1) AS fleet_avg_oem_line_stop_min,
       ROUND(AVG(GREATEST(0, a.dt - p.jis_buffer_min) * p.line_stop_charge_usd_per_min), 0) AS fleet_avg_charge_usd_per_failure
FROM pdm_raw.line_programs p CROSS JOIN avg_dt a"""))
