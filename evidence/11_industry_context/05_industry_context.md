# Executed notebook: 05_industry_context

Exported from Databricks job run `517479541358465` (task `industry_context`, task run `222724314415679`).

Result: **SUCCESS** · start 2026-10-09T16:36:41.376000+00:00 · end 2026-10-09T16:37:36.248000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/233410447833891/run/517479541358465


# 05 · Industry context: Tier-1 EV battery enclosure supplier

Volta Industrial (fictional) makes aluminum battery enclosures for EV OEMs. Each of its 12 lines builds one
part family for one OEM vehicle program and ships **just-in-sequence (JIS)**. If a station fails for longer than the
JIS buffer, the OEM's assembly line stops and the supplier is charged for every minute.

This notebook adds that context to the governed data, so risk is expressed in the supplier's own terms:
* `pdm_raw.line_programs`: OEM customer, vehicle program, part family, JIS buffer and contract line-stop charge per line.
* `pdm_raw.process_steps`: the enclosure process step and critical quality characteristic behind each station position.
* `pdm_ops.oem_delivery_exposure`: per line, live risk joined to the OEM contract. It answers "if the riskiest station
  fails now, does the OEM line stop, and what does it cost us?"

All OEMs, programs and contract terms are synthetic.

```python
dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("app_sp", "2a9b01a6-1050-4c7d-b389-45351bf8e97b")
CATALOG = dbutils.widgets.get("catalog")
APP_SP = dbutils.widgets.get("app_sp")
spark.sql(f"USE CATALOG {CATALOG}")
```

Output:

```text
{"text/plain": "DataFrame[]"}
```

## OEM programs per line (synthetic contract terms)

```python
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
```

Output:

| line_id | oem_customer | vehicle_program | part_family | jis_buffer_min | line_stop_charge_usd_per_min | enclosures_per_hour |
|---|---|---|---|---|---|---|
| PLT-E-A | Aurora Elbil | Aurora A3 Hatch | Battery tray (lower housing) | 60 | 11000 | 45 |
| PLT-E-B | Aurora Elbil | Aurora A3 Hatch | Battery cover (upper housing) | 75 | 11000 | 45 |
| PLT-E-C | Aurora Elbil | Aurora X5 SUV | Battery tray (lower housing) | 45 | 16000 | 34 |
| PLT-E-D | Nordvik Motors | NV-e5 Crossover | Cooling plate assembly | 90 | 9000 | 48 |
| PLT-N-A | Nordvik Motors | NV-e7 SUV | Battery tray (lower housing) | 60 | 15000 | 42 |
| PLT-N-B | Nordvik Motors | NV-e7 SUV | Battery cover (upper housing) | 75 | 15000 | 42 |
| PLT-N-C | Nordvik Motors | NV-e5 Crossover | Battery tray (lower housing) | 60 | 12000 | 36 |
| PLT-N-D | Fjord Electric | FE Pace Sedan | Cooling plate assembly | 90 | 9000 | 48 |
| PLT-S-A | Fjord Electric | FE Pace Sedan | Battery tray (lower housing) | 45 | 18000 | 40 |
| PLT-S-B | Fjord Electric | FE Pace Sedan | Battery cover (upper housing) | 60 | 18000 | 40 |
| PLT-S-C | Fjord Electric | FE Haul Van | Battery tray (lower housing) | 75 | 10000 | 30 |
| PLT-S-D | Aurora Elbil | Aurora A3 Hatch | Cooling plate assembly | 90 | 8000 | 50 |

## Enclosure process step per station position
Every line has the same 8-station flow. The station types in the simulator map to these steps.

```python
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
```

Output:

| station_position | station_type | process_step | critical_quality_characteristic |
|---|---|---|---|
| 1 | press | Stamping of tray floor and side members | Dimensional accuracy of formed parts |
| 2 | cnc_mill | Machining of extrusion profiles | Hole position for module mounting |
| 3 | welder | Friction-stir welding of frame | Weld seam integrity (crash load path) |
| 4 | robot_arm | Sealant dispensing and handling | Bead continuity (IP67 sealing) |
| 5 | conveyor | Transfer to leak test | Takt and part sequence |
| 6 | cnc_mill | Flatness machining of cooling interface | Flatness of thermal interface |
| 7 | welder | Laser welding of cover brackets | Weld penetration |
| 8 | press | Clinching and end-of-line press | Joint strength before JIS shipment |

## OEM delivery exposure per line (live)
* `typical_unplanned_downtime_min`: average corrective-repair downtime for the riskiest station's type, from the maintenance log.
* `oem_line_stop_min_if_fails`: downtime beyond the JIS buffer. This is how long the OEM's line would stand still.
* `exposure_usd_if_fails`: those minutes times the contract line-stop charge.

```python
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
```

Output:

```text
granted SELECT on TABLE pdm_raw.line_programs to app SP 2a9b01a6-1050-4c7d-b389-45351bf8e97b
granted SELECT on TABLE pdm_raw.process_steps to app SP 2a9b01a6-1050-4c7d-b389-45351bf8e97b
granted SELECT on TABLE pdm_ops.oem_delivery_exposure to app SP 2a9b01a6-1050-4c7d-b389-45351bf8e97b
```

### Exposure right now, riskiest lines first

```python
display(spark.sql("""
SELECT line_id, oem_customer, vehicle_program, riskiest_station_id, riskiest_process_step, riskiest_risk_band,
       ROUND(riskiest_failure_probability * 100, 1) AS risk_pct, jis_buffer_min, typical_unplanned_downtime_min,
       oem_line_stop_min_if_fails, exposure_usd_if_fails, risk_weighted_exposure_usd
FROM pdm_ops.oem_delivery_exposure ORDER BY risk_weighted_exposure_usd DESC, line_id"""))
```

Output:

| line_id | oem_customer | vehicle_program | riskiest_station_id | riskiest_process_step | riskiest_risk_band | risk_pct | jis_buffer_min | typical_unplanned_downtime_min | oem_line_stop_min_if_fails | exposure_usd_if_fails | risk_weighted_exposure_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PLT-S-B | Fjord Electric | FE Pace Sedan | PLT-S-B01 | Stamping of tray floor and side members | HIGH | 99.7 | 60 | 111.0 | 51.0 | 915074.0 | 912604.0 |
| PLT-N-C | Nordvik Motors | NV-e5 Crossover | PLT-N-C01 | Stamping of tray floor and side members | HIGH | 99.9 | 60 | 111.0 | 51.0 | 610050.0 | 609440.0 |
| PLT-E-A | Aurora Elbil | Aurora A3 Hatch | PLT-E-A02 | Machining of extrusion profiles | ELEVATED | 48.4 | 60 | 115.0 | 55.0 | 607174.0 | 293812.0 |
| PLT-E-C | Aurora Elbil | Aurora X5 SUV | PLT-E-C04 | Sealant dispensing and handling | NORMAL | 12.5 | 45 | 109.0 | 64.0 | 1021610.0 | 128110.0 |
| PLT-E-D | Nordvik Motors | NV-e5 Crossover | PLT-E-D07 | Laser welding of cover brackets | ELEVATED | 51.4 | 90 | 113.0 | 23.0 | 202536.0 | 104205.0 |
| PLT-S-C | Fjord Electric | FE Haul Van | PLT-S-C02 | Machining of extrusion profiles | NORMAL | 25.3 | 75 | 115.0 | 40.0 | 401976.0 | 101620.0 |
| PLT-S-A | Fjord Electric | FE Pace Sedan | PLT-S-A06 | Flatness machining of cooling interface | NORMAL | 5.4 | 45 | 115.0 | 70.0 | 1263557.0 | 68232.0 |
| PLT-N-B | Nordvik Motors | NV-e7 SUV | PLT-N-B01 | Stamping of tray floor and side members | NORMAL | 8.3 | 75 | 111.0 | 36.0 | 537562.0 | 44403.0 |
| PLT-N-A | Nordvik Motors | NV-e7 SUV | PLT-N-A06 | Flatness machining of cooling interface | NORMAL | 5.1 | 60 | 115.0 | 55.0 | 827965.0 | 42392.0 |
| PLT-E-B | Aurora Elbil | Aurora A3 Hatch | PLT-E-B01 | Stamping of tray floor and side members | NORMAL | 4.5 | 75 | 111.0 | 36.0 | 394212.0 | 17542.0 |
| PLT-S-D | Aurora Elbil | Aurora A3 Hatch | PLT-S-D01 | Stamping of tray floor and side members | NORMAL | 9.8 | 90 | 111.0 | 21.0 | 166700.0 | 16387.0 |
| PLT-N-D | Fjord Electric | FE Pace Sedan | PLT-N-D08 | Clinching and end-of-line press | NORMAL | 4.7 | 90 | 111.0 | 21.0 | 187537.0 | 8852.0 |

### Exposure per OEM customer
The supplier scorecard is kept per OEM. This is the view a COO takes into the customer review.

```python
display(spark.sql("""
SELECT oem_customer, COUNT(*) AS lines, SUM(high_risk_stations) AS high_risk_stations,
       SUM(exposure_usd_if_fails) AS exposure_usd_if_riskiest_fail, SUM(risk_weighted_exposure_usd) AS risk_weighted_exposure_usd
FROM pdm_ops.oem_delivery_exposure GROUP BY ALL ORDER BY risk_weighted_exposure_usd DESC"""))
```

Output:

| oem_customer | lines | high_risk_stations | exposure_usd_if_riskiest_fail | risk_weighted_exposure_usd |
|---|---|---|---|---|
| Fjord Electric | 4 | 1 | 2768144.0 | 1091308.0 |
| Nordvik Motors | 4 | 1 | 2178113.0 | 800440.0 |
| Aurora Elbil | 4 | 0 | 2189696.0 | 455851.0 |

### Contract exposure of one unplanned failure, per line (independent of the current risk)
Uses the fleet-average corrective downtime. This feeds the value model in `presentation/deck.md`.

```python
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
```

Output:

| line_id | oem_customer | vehicle_program | jis_buffer_min | avg_unplanned_downtime_min | oem_line_stop_min | charge_usd_per_failure |
|---|---|---|---|---|---|---|
| PLT-E-A | Aurora Elbil | Aurora A3 Hatch | 60 | 112.0 | 52.0 | 575201.0 |
| PLT-E-B | Aurora Elbil | Aurora A3 Hatch | 75 | 112.0 | 37.0 | 410201.0 |
| PLT-E-C | Aurora Elbil | Aurora X5 SUV | 45 | 112.0 | 67.0 | 1076656.0 |
| PLT-E-D | Nordvik Motors | NV-e5 Crossover | 90 | 112.0 | 22.0 | 200619.0 |
| PLT-N-A | Nordvik Motors | NV-e7 SUV | 60 | 112.0 | 52.0 | 784365.0 |
| PLT-N-B | Nordvik Motors | NV-e7 SUV | 75 | 112.0 | 37.0 | 559365.0 |
| PLT-N-C | Nordvik Motors | NV-e5 Crossover | 60 | 112.0 | 52.0 | 627492.0 |
| PLT-N-D | Fjord Electric | FE Pace Sedan | 90 | 112.0 | 22.0 | 200619.0 |
| PLT-S-A | Fjord Electric | FE Pace Sedan | 45 | 112.0 | 67.0 | 1211238.0 |
| PLT-S-B | Fjord Electric | FE Pace Sedan | 60 | 112.0 | 52.0 | 941238.0 |
| PLT-S-C | Fjord Electric | FE Haul Van | 75 | 112.0 | 37.0 | 372910.0 |
| PLT-S-D | Aurora Elbil | Aurora A3 Hatch | 90 | 112.0 | 22.0 | 178328.0 |

Output:

| fleet_avg_oem_line_stop_min | fleet_avg_charge_usd_per_failure |
|---|---|
| 43.5 | 594853.0 |
