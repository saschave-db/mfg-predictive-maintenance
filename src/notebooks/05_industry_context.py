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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scorecard KPIs: what moves for the COO and the Head of Maintenance & Reliability
# MAGIC Every number on the deck's scorecard and value slides is computed here from the maintenance history
# MAGIC (`source = 'history'`) and the OEM contract terms above. The business assumptions are widgets, so finance can
# MAGIC replace them with actuals and re-run.
# MAGIC * **Measured in the data:** repair counts, downtime and parts cost per repair type, JIS buffers, line-stop charges.
# MAGIC * **Measured by the model** (`evidence/04_training/02_train_model.md`): alert precision 0.95 at the HIGH threshold.
# MAGIC * **Assumptions:** failures per station per year, share converted to planned repairs, internal downtime cost,
# MAGIC   share of unplanned failures that reach the OEM, operating hours per line.

# COMMAND ----------

dbutils.widgets.text("failures_per_station_year", "2")
dbutils.widgets.text("conversion", "0.7")
dbutils.widgets.text("downtime_cost_usd_per_hour", "15000")
dbutils.widgets.text("oem_escape_share", "0.05")
dbutils.widgets.text("alert_precision", "0.95")
dbutils.widgets.text("operating_hours_per_line_year", "6000")
A = {k: float(dbutils.widgets.get(k)) for k in ("failures_per_station_year", "conversion", "downtime_cost_usd_per_hour",
                                                "oem_escape_share", "alert_precision", "operating_hours_per_line_year")}
print("assumptions:", A)

h = {r.event_type: r for r in spark.sql("""
SELECT event_type, COUNT(*) AS n, SUM(downtime_min) AS dt, SUM(parts_cost_usd) AS parts
FROM pdm_core.maintenance_events WHERE source = 'history' AND event_type IN ('corrective_repair', 'preventive_repair')
GROUP BY event_type""").collect()}
c, p = h["corrective_repair"], h["preventive_repair"]
avg_c_dt, avg_p_dt = c.dt / c.n, p.dt / p.n
avg_c_parts, avg_p_parts = c.parts / c.n, p.parts / p.n
avg_charge = spark.sql(f"""
SELECT CAST(AVG(GREATEST(0, {avg_c_dt} - jis_buffer_min) * line_stop_charge_usd_per_min) AS DOUBLE) AS v,
       CAST(AVG(GREATEST(0, {avg_c_dt} - jis_buffer_min)) AS DOUBLE) AS m, MIN(jis_buffer_min) AS bmin, MAX(jis_buffer_min) AS bmax,
       COUNT(*) AS lines FROM pdm_raw.line_programs""").first()
stations = spark.table("pdm_raw.station_master").count()
print(f"history: {c.n} corrective repairs (avg {avg_c_dt:.1f} min, ${avg_c_parts:,.0f}), "
      f"{p.n} preventive repairs (avg {avg_p_dt:.1f} min, ${avg_p_parts:,.0f}); {stations} stations, {avg_charge.lines} lines")
print(f"JIS buffers {avg_charge.bmin} to {avg_charge.bmax} min; avg OEM line stop per unplanned failure "
      f"{avg_charge.m:.1f} min; avg contract charge ${avg_charge.v:,.0f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Henrik Lindqvist (Head of Maintenance & Reliability): monthly operations review KPIs
# MAGIC Same maintenance history, with the assumed share of failures converted into planned repairs.

# COMMAND ----------

conv_n = round(c.n * A["conversion"])
c2, p2 = c.n - conv_n, p.n + conv_n
rows = [
    ("Planned maintenance share (% of repairs)", 100 * p.n / (c.n + p.n), 100 * p2 / (c2 + p2)),
    ("Mean repair time per maintenance event (min)", (c.dt + p.dt) / (c.n + p.n),
     (c2 * avg_c_dt + p2 * avg_p_dt) / (c2 + p2)),
    ("Maintenance parts spend (USD, same history)", c.parts + p.parts, c2 * avg_c_parts + p2 * avg_p_parts),
    ("Unplanned (corrective) repairs", float(c.n), float(c2)),
]
display(spark.createDataFrame([(k, round(a, 1), round(b, 1), round(100 * (b - a) / a, 1)) for k, a, b in rows],
                              "kpi string, today double, with_conversion double, change_pct double"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Value model: layer 1 (Volta's own P&L) and layer 2 (OEM line-stop charges avoided)

# COMMAND ----------

def value(conversion, cost_per_hour, escape):
    failures = stations * A["failures_per_station_year"]
    n = failures * conversion
    saved_min, saved_parts = avg_c_dt - avg_p_dt, avg_c_parts - avg_p_parts
    false_alarms = n / A["alert_precision"] - n
    l1 = (n * saved_min / 60 * cost_per_hour + n * saved_parts
          - false_alarms * (avg_p_parts + avg_p_dt / 60 * cost_per_hour))
    l2 = failures * escape * conversion * avg_charge.v
    return dict(failures=failures, converted=n, downtime_h_avoided=n * saved_min / 60,
                downtime_usd=n * saved_min / 60 * cost_per_hour, parts_usd=n * saved_parts,
                false_alarms=false_alarms, layer1_net_usd=l1, oem_stops=failures * escape, layer2_usd=l2)

base = value(A["conversion"], A["downtime_cost_usd_per_hour"], A["oem_escape_share"])
lines = avg_charge.lines
base["oee_availability_pts"] = 100 * base["downtime_h_avoided"] / (lines * A["operating_hours_per_line_year"])
display(spark.createDataFrame([(k, round(float(v), 2)) for k, v in base.items()], "metric string, base_case double"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Sensitivity
# MAGIC Layer 1 by conversion share and internal downtime cost. Layer 2 by the share of unplanned failures that reach the OEM.

# COMMAND ----------

display(spark.createDataFrame(
    [(f"{int(cv * 100)}%", *[round(value(cv, ch, A["oem_escape_share"])["layer1_net_usd"] / 1e6, 1) for ch in (5000, 15000, 50000)])
     for cv in (0.5, 0.7, 0.9)],
    "converted_to_planned string, layer1_musd_at_5k_per_h double, layer1_musd_at_15k_per_h double, layer1_musd_at_50k_per_h double"))
display(spark.createDataFrame(
    [(f"{int(e * 100)}%", round(value(A["conversion"], A["downtime_cost_usd_per_hour"], e)["oem_stops"], 1),
      round(value(A["conversion"], A["downtime_cost_usd_per_hour"], e)["layer2_usd"] / 1e6, 1)) for e in (0.02, 0.05, 0.10)],
    "share_reaching_oem string, oem_stops_per_year double, layer2_musd_avoided double"))
