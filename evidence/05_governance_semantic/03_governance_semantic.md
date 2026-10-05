# Executed notebook: 03_governance_semantic

Exported from Databricks job run `50596819223088` (task `governance`, task run `255046613956180`).

Result: **SUCCESS** · start 2026-10-05T22:34:05.473000+00:00 · end 2026-10-05T22:35:00.130000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/438031727317059/run/50596819223088


# 03 · Governance and semantic layer
* **Work orders from Lakebase:** Lakehouse Sync streams Postgres changes into `pdm_ops.lb_work_orders_history` (SCD2 CDC).
  A view exposes the current state of each work order.
* **Metric views:** governed KPI definitions shared by Genie, dashboards and SQL.
* **Fine-grained access:** PII column masks and a plant-level row filter on technicians, plus tags.

```python
dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
CATALOG = dbutils.widgets.get("catalog")
OWNER = spark.sql("SELECT current_user()").first()[0]
spark.sql(f"USE CATALOG {CATALOG}")


def run(sql):
    try:
        spark.sql(sql)
        print("OK  ", " ".join(sql.split())[:150])
    except Exception as e:
        print("FAIL", " ".join(sql.split())[:150], "->", str(e).splitlines()[0][:200])
```

## Current work orders (from Lakebase via Lakehouse Sync)

```python
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
```

Output:

```text
OK   CREATE OR REPLACE VIEW pdm_ops.work_orders_current COMMENT 'Current state of maintenance work orders created in the Plant Health Live app (Lakebase ->
```

Output:

| status | work_orders |
|---|---|

## Metric views

```python
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
```

Output:

```text
OK   CREATE OR REPLACE VIEW pdm_ops.maintenance_metrics WITH METRICS LANGUAGE YAML AS $$ version: 1.1 source: serverless_stable_am1uc2_catalog.pdm_core.mai
OK   CREATE OR REPLACE VIEW pdm_ops.station_risk_metrics WITH METRICS LANGUAGE YAML AS $$ version: 1.1 source: serverless_stable_am1uc2_catalog.pdm_core.st
OK   CREATE OR REPLACE VIEW pdm_ops.work_order_metrics WITH METRICS LANGUAGE YAML AS $$ version: 1.1 source: serverless_stable_am1uc2_catalog.pdm_ops.work_
```

Output:

| namespace | viewName | isTemporary | isMaterialized | isMetric |
|---|---|---|---|---|
| pdm_ops | maintenance_metrics | False | False | True |
| pdm_ops | station_risk_metrics | False | False | True |
| pdm_ops | work_order_metrics | False | False | True |
| pdm_ops | work_orders_current | False | False | False |

```python
display(spark.sql("""
SELECT `Station Type`, MEASURE(Failures) AS failures, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min,
       MEASURE(`Preventive Share`) AS preventive_share, MEASURE(`Parts Cost USD`) AS parts_cost_usd
FROM pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY failures DESC"""))
```

Output:

| Station Type | failures | mttr_min | preventive_share | parts_cost_usd |
|---|---|---|---|---|
| cnc_mill | 296 | 115.1976376037942 | 0.1828254847645429 | 2165065.4045573804 |
| press | 280 | 110.83746264557489 | 0.2112676056338028 | 2078142.541507669 |
| welder | 260 | 112.50394617635841 | 0.2121212121212121 | 1925990.7829069379 |
| robot_arm | 137 | 108.85064914589415 | 0.1746987951807229 | 1022546.4169817847 |
| conveyor | 124 | 112.01279122873008 | 0.1842105263157895 | 932377.9080414224 |

```python
display(spark.sql("""
SELECT Plant, MEASURE(`Stations At High Risk`) AS high_risk_stations, MEASURE(`Avg Failure Probability`) AS avg_risk,
       MEASURE(`Avg Sensor To Score Latency Seconds`) AS latency_s, MEASURE(`Latest Score Time`) AS latest
FROM pdm_ops.station_risk_metrics WHERE `Score Time` > current_timestamp() - INTERVAL 10 MINUTES
GROUP BY ALL ORDER BY Plant"""))
```

Output:

| Plant | high_risk_stations | avg_risk | latency_s | latest |
|---|---|---|---|---|
| Plant East | 15 | 0.06977223011363637 | 201.0460909090909 | 2026-10-05T22:32:30.000Z |
| Plant North | 12 | 0.06569396306818186 | 201.0460909090909 | 2026-10-05T22:32:30.000Z |
| Plant South | 9 | 0.05399509943181811 | 201.0460909090909 | 2026-10-05T22:32:30.000Z |

## Fine-grained access control and tags
* `email` / `phone` are masked unless the reader is in `pdm_supervisors`.
* Technicians are filtered to the reader's plant group (`pdm_plant_n|s|e`); `pdm_all_plants` and the demo owner see all.

```python
run("""CREATE OR REPLACE FUNCTION pdm_ops.mask_pii(v STRING) RETURNS STRING
       COMMENT 'Reveal PII only to members of pdm_supervisors'
       RETURN CASE WHEN is_account_group_member('pdm_supervisors') THEN v ELSE '***redacted***' END""")
run(f"""CREATE OR REPLACE FUNCTION pdm_ops.plant_row_filter(plant_id STRING) RETURNS BOOLEAN
       COMMENT 'Plant managers see their own plant; pdm_all_plants and the demo owner see everything'
       RETURN is_account_group_member('pdm_all_plants') OR current_user() = '{OWNER}'
              OR is_account_group_member(concat('pdm_plant_', lower(substr(plant_id, 5, 1))))""")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET MASK pdm_ops.mask_pii")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET MASK pdm_ops.mask_pii")
run("ALTER TABLE pdm_raw.technicians SET ROW FILTER pdm_ops.plant_row_filter ON (home_plant_id)")

for schema in ["pdm_raw", "pdm_core", "pdm_ml", "pdm_ops"]:
    run(f"ALTER SCHEMA {schema} SET TAGS ('domain' = 'manufacturing', 'use_case' = 'predictive_maintenance', 'data_class' = 'synthetic')")
run("ALTER TABLE pdm_raw.sensor_readings SET TAGS ('source' = 'zerobus', 'latency_tier' = 'realtime')")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET TAGS ('pii' = 'email')")
run("ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET TAGS ('pii' = 'phone')")
```

Output:

```text
OK   CREATE OR REPLACE FUNCTION pdm_ops.mask_pii(v STRING) RETURNS STRING COMMENT 'Reveal PII only to members of pdm_supervisors' RETURN CASE WHEN is_accou
OK   CREATE OR REPLACE FUNCTION pdm_ops.plant_row_filter(plant_id STRING) RETURNS BOOLEAN COMMENT 'Plant managers see their own plant; pdm_all_plants and t
OK   ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET MASK pdm_ops.mask_pii
OK   ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET MASK pdm_ops.mask_pii
OK   ALTER TABLE pdm_raw.technicians SET ROW FILTER pdm_ops.plant_row_filter ON (home_plant_id)
FAIL ALTER SCHEMA pdm_raw SET TAGS ('domain' = 'manufacturing', 'use_case' = 'predictive_maintenance', 'data_class' = 'synthetic') -> [RequestId=6933be5b-74c7-4fda-a2e4-2538842abe3b ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value manufacturing is not an allowed value for tag policy key domain. Allowed v
FAIL ALTER SCHEMA pdm_core SET TAGS ('domain' = 'manufacturing', 'use_case' = 'predictive_maintenance', 'data_class' = 'synthetic') -> [RequestId=912e6391-db1a-42f0-8ac0-69d968831108 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value manufacturing is not an allowed value for tag policy key domain. Allowed v
FAIL ALTER SCHEMA pdm_ml SET TAGS ('domain' = 'manufacturing', 'use_case' = 'predictive_maintenance', 'data_class' = 'synthetic') -> [RequestId=fb44d98a-1d3a-410e-b138-412c7b26dae0 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value manufacturing is not an allowed value for tag policy key domain. Allowed v
FAIL ALTER SCHEMA pdm_ops SET TAGS ('domain' = 'manufacturing', 'use_case' = 'predictive_maintenance', 'data_class' = 'synthetic') -> [RequestId=bfe6a1a3-4522-4b53-9c09-4ba1adaf12bf ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value manufacturing is not an allowed value for tag policy key domain. Allowed v
FAIL ALTER TABLE pdm_raw.sensor_readings SET TAGS ('source' = 'zerobus', 'latency_tier' = 'realtime') -> [RequestId=ce51d425-12e1-4e0e-8c7d-43e058099eb7 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value zerobus is not an allowed value for tag policy key source. Allowed values:
FAIL ALTER TABLE pdm_raw.technicians ALTER COLUMN email SET TAGS ('pii' = 'email') -> [RequestId=2e356ce8-0be3-4dbf-a526-bc0dffe98e5b ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value email is not an allowed value for tag policy key pii. Allowed values: [ssn
FAIL ALTER TABLE pdm_raw.technicians ALTER COLUMN phone SET TAGS ('pii' = 'phone') -> [RequestId=ed70c39b-ff5f-4804-8202-8eadbada58cb ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value phone is not an allowed value for tag policy key pii. Allowed values: [ssn
```

```python
# The owner is exempt from the row filter but not in pdm_supervisors, so rows are visible and PII is masked.
display(spark.sql("SELECT technician_id, full_name, home_plant_id, email, phone FROM pdm_raw.technicians ORDER BY technician_id LIMIT 6"))
display(spark.sql(f"""SELECT tag_name, tag_value, count(*) AS objects FROM {CATALOG}.information_schema.schema_tags
                      WHERE schema_name LIKE 'pdm_%' GROUP BY ALL"""))
```

Output:

| technician_id | full_name | home_plant_id | email | phone |
|---|---|---|---|---|
| T001 | Jamie Brennan | PLT-N | ***redacted*** | ***redacted*** |
| T002 | Jamie Brennan | PLT-S | ***redacted*** | ***redacted*** |
| T003 | Taylor Lindqvist | PLT-E | ***redacted*** | ***redacted*** |
| T004 | Jamie Iyer | PLT-N | ***redacted*** | ***redacted*** |
| T005 | Sam Haddad | PLT-S | ***redacted*** | ***redacted*** |
| T006 | Jordan Okafor | PLT-E | ***redacted*** | ***redacted*** |

Output:

| tag_name | tag_value | objects |
|---|---|---|
