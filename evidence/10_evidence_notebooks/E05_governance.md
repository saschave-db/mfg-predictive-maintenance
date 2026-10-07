# Executed notebook: E05_governance

Exported from Databricks job run `994447175034582` (task `E05_governance`, task run `748346428709987`).

Result: **SUCCESS** · start 2026-10-07T23:14:43.094000+00:00 · end 2026-10-07T23:16:22.209000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


# E05 · Unity Catalog governance and the semantic layer

**What was built** (notebook `03_governance_semantic`):
* Least-privilege grants: Zerobus SP (write bronze only), app SP (read gold + metric views).
* PII column masks on technician `email` / `phone` (`pdm_ops.mask_pii`), plant row filter (`pdm_ops.plant_row_filter`).
* Tags on schemas, tables and PII columns (`pdm_` keys; the workspace enforces governed policies on `domain`, `source`, `pii`).
* Metric views `maintenance_metrics`, `station_risk_metrics`, `work_order_metrics` with synonyms for Genie.
* The model is a UC securable (`pdm_ml.station_failure_model`) with alias `@champion`.

**What this notebook proves.** Each control as recorded in Unity Catalog, and that the row filter and masks are
**enforced on a non-owner identity**: the app's service principal. Owners are often exempt, so the owner's view alone
proves little. Section 2b shows the SP's own queries (from query history) and what Unity Catalog returned to it.

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
APP_SP = w.apps.get(APP_NAME).service_principal_client_id
```

## 1 · Grants for the two service principals

```python
display(spark.sql(f"SHOW GRANTS `{ZEROBUS_SP}` ON TABLE pdm_raw.sensor_readings"))
for obj in ["SCHEMA pdm_core", "SCHEMA pdm_ops", "TABLE pdm_raw.station_master"]:
    display(spark.sql(f"SHOW GRANTS `{APP_SP}` ON {obj}"))
```

Output:

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 240a5501-f956-4282-a2a7-ccc7614683a7 | MODIFY | TABLE | serverless_stable_am1uc2_catalog.pdm_raw.sensor_readings |
| 240a5501-f956-4282-a2a7-ccc7614683a7 | SELECT | TABLE | serverless_stable_am1uc2_catalog.pdm_raw.sensor_readings |

Output:

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | SELECT | SCHEMA | serverless_stable_am1uc2_catalog.pdm_core |
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | USE SCHEMA | SCHEMA | serverless_stable_am1uc2_catalog.pdm_core |

Output:

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | SELECT | SCHEMA | serverless_stable_am1uc2_catalog.pdm_ops |
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | USE SCHEMA | SCHEMA | serverless_stable_am1uc2_catalog.pdm_ops |

Output:

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | SELECT | TABLE | serverless_stable_am1uc2_catalog.pdm_raw.station_master |

## 2 · Column masks and row filter

```python
display(spark.sql(f"""SELECT table_schema, table_name, column_name, mask_name FROM {CATALOG}.information_schema.column_masks
                      WHERE table_schema LIKE 'pdm_%'"""))
display(spark.sql(f"""SELECT table_schema, table_name, filter_name, target_columns FROM {CATALOG}.information_schema.row_filters
                      WHERE table_schema LIKE 'pdm_%'"""))
print("Effect for the current user (owner: exempt from row filter, not in pdm_supervisors):")
display(spark.sql("SELECT technician_id, full_name, home_plant_id, email, phone FROM pdm_raw.technicians ORDER BY technician_id LIMIT 6"))
print("Function bodies:")
for f in ["pdm_ops.mask_pii", "pdm_ops.plant_row_filter"]:
    print(spark.sql(f"DESCRIBE FUNCTION EXTENDED {f}").filter("function_desc LIKE 'Body:%' OR function_desc LIKE 'Function:%'").toPandas().to_string(index=False))
```

Output:

| table_schema | table_name | column_name | mask_name |
|---|---|---|---|
| pdm_raw | technicians | phone | serverless_stable_am1uc2_catalog.pdm_ops.mask_pii |
| pdm_raw | technicians | email | serverless_stable_am1uc2_catalog.pdm_ops.mask_pii |

Output:

| table_schema | table_name | filter_name | target_columns |
|---|---|---|---|
| pdm_raw | technicians | serverless_stable_am1uc2_catalog.pdm_ops.plant_row_filter | home_plant_id |

Output:

```text
Effect for the current user (owner: exempt from row filter, not in pdm_supervisors):
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

```text
Function bodies:
                                                                                       function_desc
                                    Function:      serverless_stable_am1uc2_catalog.pdm_ops.mask_pii
Body:          CASE WHEN is_account_group_member('pdm_supervisors') THEN v ELSE '***redacted***' END
                                                                                                                                                                                                                          function_desc
                                                                                                                                                               Function:      serverless_stable_am1uc2_catalog.pdm_ops.plant_row_filter
Body:          current_user() = 'sascha.vetter@databricks.com' OR is_account_group_member('pdm_all_plants')\n              OR EXISTS (SELECT 1 FROM pdm_ops.plant_access a WHERE a.principal = current_user() AND a.plant_id = p_plant)
```

## 2b · Enforcement on a non-owner identity: the app's service principal
The app endpoint `/api/governance/technicians` runs `SELECT current_user(), ... FROM pdm_raw.technicians` on the SQL
warehouse **as the app SP**. The SP has `SELECT` on the table, is granted only `PLT-N` in `pdm_ops.plant_access`, and is
not in `pdm_supervisors`. Expected: 6 of 18 technicians (Plant North only), email and phone redacted.
The raw HTTP response of that call is in `evidence/08_app/governance_as_app_sp.json`.

```python
display(spark.sql("SELECT * FROM pdm_ops.plant_access"))
print("Row filter function as deployed:")
print(spark.sql("DESCRIBE FUNCTION EXTENDED pdm_ops.plant_row_filter").filter("function_desc LIKE 'Body:%'").first()[0])
print("\nOwner view for contrast (owner is exempt from the filter, masks still apply because the owner is not a supervisor):")
display(spark.sql("SELECT home_plant_id, count(*) AS technicians FROM pdm_raw.technicians GROUP BY ALL ORDER BY 1"))
```

Output:

| principal | plant_id | granted_at |
|---|---|---|
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | PLT-N | 2026-10-07T22:53:47.492Z |

Output:

```text
Row filter function as deployed:
Body:          current_user() = 'sascha.vetter@databricks.com' OR is_account_group_member('pdm_all_plants')
              OR EXISTS (SELECT 1 FROM pdm_ops.plant_access a WHERE a.principal = current_user() AND a.plant_id = p_plant)

Owner view for contrast (owner is exempt from the filter, masks still apply because the owner is not a supervisor):
```

Output:

| home_plant_id | technicians |
|---|---|
| PLT-E | 6 |
| PLT-N | 6 |
| PLT-S | 6 |

```python
import json, os
from databricks.sdk.service.sql import QueryFilter
sp_user = next(w.service_principals.list(filter=f"applicationId eq {APP_SP}"))
print("app service principal:", sp_user.display_name, "| application id:", APP_SP, "| user id:", sp_user.id)
# Statement ids of the SP's calls, from the committed raw capture evidence/08_app/governance_as_app_sp.json
cap = json.load(open(os.path.abspath("../../../evidence/08_app/governance_as_app_sp.json")))
steps = {k: v for k, v in cap.items() if k.startswith("step_")}
resp = w.query_history.list(filter_by=QueryFilter(statement_ids=[v["statement_id"] for v in steps.values()]),
                            include_metrics=True, max_results=10)
by_id = {q.query_id: q for q in (getattr(resp, "res", None) or ([] if hasattr(resp, "res") else resp))}
print("\n| control step | statement_id | executed_as (from Query History) | status | rows produced | plants in app response |")
print("|---|---|---|---|---|---|")
for step, v in steps.items():
    q = by_id.get(v["statement_id"])
    print(f"| {step} | {v['statement_id']} | {q.executed_as_user_name if q else 'not found'} | {q.status.value if q else ''} | "
          f"{q.metrics.rows_produced_count if q and q.metrics else ''} | {v['plants_visible']} |")
print("\nQuery text recorded for the first statement:\n", by_id[steps['step_1_mapping_PLT_N_only']['statement_id']].query_text)
```

Output:

```text
app service principal: app-3jm8lb pdm-plant-health-live | application id: 2a9b01a6-1050-4c7d-b389-45351bf8e97b | user id: 71763000173026

| control step | statement_id | executed_as (from Query History) | status | rows produced | plants in app response |
|---|---|---|---|---|---|
| step_1_mapping_PLT_N_only | 01f1c2a2-15d6-1609-83d7-b6f2191e0df3 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 6 | ['PLT-N'] |
| step_2_after_granting_PLT_S_in_plant_access | 01f1c2a2-2e98-1b39-aac3-c40e88911df1 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 12 | ['PLT-N', 'PLT-S'] |
| step_3_after_revoking_PLT_S_again | 01f1c2a2-330e-1324-85ee-57afe1a71d57 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 6 | ['PLT-N'] |

Query text recorded for the first statement:
 <REDACTED>
```

```python
# Same statements in the audit system table (it can lag behind the Query History API).
ids = ", ".join(f"'{v['statement_id']}'" for v in steps.values())
st = spark.sql(f"""SELECT statement_id, executed_by, executed_as, execution_status, produced_rows, start_time
                   FROM system.query.history WHERE statement_id IN ({ids}) ORDER BY start_time""")
display(st) if st.count() else print("system.query.history has not ingested these statements yet (system table latency).")
```

Output:

| statement_id | executed_by | executed_as | execution_status | produced_rows | start_time |
|---|---|---|---|---|---|
| 01f1c2a2-15d6-1609-83d7-b6f2191e0df3 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 6 | 2026-10-07T22:54:43.211Z |
| 01f1c2a2-2e98-1b39-aac3-c40e88911df1 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 12 | 2026-10-07T22:55:24.748Z |
| 01f1c2a2-330e-1324-85ee-57afe1a71d57 | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | FINISHED | 6 | 2026-10-07T22:55:32.231Z |

## 3 · Tags

```python
display(spark.sql(f"SELECT schema_name, tag_name, tag_value FROM {CATALOG}.information_schema.schema_tags WHERE schema_name LIKE 'pdm_%' ORDER BY 1, 2"))
display(spark.sql(f"SELECT schema_name, table_name, tag_name, tag_value FROM {CATALOG}.information_schema.table_tags WHERE schema_name LIKE 'pdm_%'"))
display(spark.sql(f"SELECT schema_name, table_name, column_name, tag_name, tag_value FROM {CATALOG}.information_schema.column_tags WHERE schema_name LIKE 'pdm_%'"))
```

Output:

| schema_name | tag_name | tag_value |
|---|---|---|
| pdm_core | pdm_data_class | synthetic |
| pdm_core | pdm_domain | manufacturing |
| pdm_core | pdm_use_case | predictive_maintenance |
| pdm_ml | pdm_data_class | synthetic |
| pdm_ml | pdm_domain | manufacturing |
| pdm_ml | pdm_use_case | predictive_maintenance |
| pdm_ops | pdm_data_class | synthetic |
| pdm_ops | pdm_domain | manufacturing |
| pdm_ops | pdm_use_case | predictive_maintenance |
| pdm_raw | pdm_data_class | synthetic |
| pdm_raw | pdm_domain | manufacturing |
| pdm_raw | pdm_use_case | predictive_maintenance |

Output:

| schema_name | table_name | tag_name | tag_value |
|---|---|---|---|
| pdm_raw | sensor_readings | pdm_source | zerobus |
| pdm_raw | sensor_readings | pdm_latency_tier | realtime |

Output:

| schema_name | table_name | column_name | tag_name | tag_value |
|---|---|---|---|---|
| pdm_raw | technicians | phone | pdm_pii | phone |
| pdm_raw | technicians | email | pdm_pii | email |

## 4 · Metric views: definitions and KPI queries

```python
for mv in ["maintenance_metrics", "station_risk_metrics", "work_order_metrics"]:
    print(f"===== pdm_ops.{mv}")
    print(spark.sql(f"SHOW CREATE TABLE pdm_ops.{mv}").first()[0])
```

Output:

```text
===== pdm_ops.maintenance_metrics
CREATE VIEW serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics (
  Plant,
  Line,
  Station,
  Station Type,
  Criticality,
  Event Type COMMENT 'failure, corrective_repair or preventive_repair',
  Failure Mode,
  Event Date,
  Event Hour,
  Failures,
  Corrective Repairs,
  Preventive Repairs,
  Downtime Minutes,
  Parts Cost USD,
  Mean Time To Repair Minutes,
  Preventive Share,
  Stations With Failures)
COMMENT 'Reliability KPIs from the maintenance log: failures, repairs, downtime, cost. Time is compressed (1 demo minute ~ 1 operating hour).'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: serverless_stable_am1uc2_catalog.pdm_core.maintenance_events

comment: "Reliability KPIs from the maintenance log: failures, repairs, downtime,\
  \ cost. Time is compressed (1 demo minute ~ 1 operating hour)."

dimensions:
  - name: Plant
    expr: plant_name
    synonyms:
      - site
      - factory

  - name: Line
    expr: line_id
    synonyms:
      - production line

  - name: Station
    expr: station_id
    synonyms:
      - machine
      - asset
      - equipment

  - name: Station Type
    expr: station_type
    synonyms:
      - machine type
      - asset class

  - name: Criticality
    expr: criticality

  - name: Event Type
    expr: event_type
    comment: "failure, corrective_repair or preventive_repair"

  - name: Failure Mode
    expr: failure_mode
    synonyms:
      - root cause
      - fault type

  - name: Event Date
    expr: event_date

  - name: Event Hour
    expr: "DATE_TRUNC('HOUR', event_ts)"

measures:
  - name: Failures
    expr: COUNT(1) FILTER (WHERE event_type = 'failure')
    synonyms:
      - breakdowns
      - unplanned stops

  - name: Corrective Repairs
    expr: COUNT(1) FILTER (WHERE event_type = 'corrective_repair')

  - name: Preventive Repairs
    expr: COUNT(1) FILTER (WHERE event_type = 'preventive_repair')
    synonyms:
      - planned maintenance

  - name: Downtime Minutes
    expr: SUM(downtime_min)
    format:
      type: number
      decimal_places:
        type: exact
        places: 0

  - name: Parts Cost USD
    expr: SUM(parts_cost_usd)
    format:
      type: currency
      currency_code: USD

  - name: Mean Time To Repair Minutes
    expr: AVG(downtime_min) FILTER (WHERE event_type = 'corrective_repair')
    synonyms:
      - MTTR

  - name: Preventive Share
    expr: "COUNT(1) FILTER (WHERE event_type = 'preventive_repair') * 1.0 / NULLIF(COUNT(1)\
      \ FILTER (WHERE event_type IN ('preventive_repair', 'corrective_repair')), 0)"
    format:
      type: percentage

  - name: Stations With Failures
    expr: COUNT(DISTINCT station_id) FILTER (WHERE event_type = 'failure')
$$

===== pdm_ops.station_risk_metrics
CREATE VIEW serverless_stable_am1uc2_catalog.pdm_ops.station_risk_metrics (
  Plant,
  Line,
  Station,
  Station Type,
  Criticality,
  Risk Band COMMENT 'NORMAL (<40%), ELEVATED (40-70%), HIGH (>=70%), DOWN (stopped)',
  Top Signal,
  Score Minute,
  Score Time,
  Avg Failure Probability,
  Max Failure Probability,
  Scored Windows,
  High Risk Windows,
  Stations At High Risk,
  Stations Down,
  Latest Score Time,
  Avg Sensor To Score Latency Seconds COMMENT 'Seconds from the newest sensor reading in a window to its risk score being written.')
COMMENT 'Live predicted failure risk per station, scored every 10 s by the SDP pipeline with the UC model @champion.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: serverless_stable_am1uc2_catalog.pdm_core.station_risk_scores

joins:
  - name: dim_station
    source: serverless_stable_am1uc2_catalog.pdm_raw.station_master
    "on": source.station_id = dim_station.station_id

comment: "Live predicted failure risk per station, scored every 10 s by the SDP pipeline\
  \ with the UC model @champion."

dimensions:
  - name: Plant
    expr: dim_station.plant_name
    synonyms:
      - site
      - factory

  - name: Line
    expr: source.line_id

  - name: Station
    expr: source.station_id
    synonyms:
      - machine
      - asset

  - name: Station Type
    expr: source.station_type

  - name: Criticality
    expr: source.criticality

  - name: Risk Band
    expr: source.risk_band
    comment: "NORMAL (<40%), ELEVATED (40-70%), HIGH (>=70%), DOWN (stopped)"

  - name: Top Signal
    expr: source.top_signal
    synonyms:
      - driver
      - main contributor
      - anomalous sensor

  - name: Score Minute
    expr: "DATE_TRUNC('MINUTE', source.window_end)"

  - name: Score Time
    expr: source.window_end

measures:
  - name: Avg Failure Probability
    expr: AVG(source.failure_probability)
    format:
      type: percentage
    synonyms:
      - risk
      - maintenance probability

  - name: Max Failure Probability
    expr: MAX(source.failure_probability)
    format:
      type: percentage

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
    expr: AVG(unix_millis(source.scored_at) - unix_millis(source.last_reading_ts))
      / 1000.0
    comment: Seconds from the newest sensor reading in a window to its risk score
      being written.
    synonyms:
      - pipeline latency
      - freshness
$$

===== pdm_ops.work_order_metrics
CREATE VIEW serverless_stable_am1uc2_catalog.pdm_ops.work_order_metrics (
  Plant,
  Line,
  Station,
  Station Type,
  Priority,
  Status,
  Risk Band At Creation,
  Top Signal At Creation,
  Created Date,
  Work Orders,
  Open Work Orders,
  Completed Work Orders,
  Avg Risk At Creation,
  Avg Minutes To Complete)
COMMENT 'Maintenance work orders raised from live risk alerts in the Plant Health Live app.'
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: serverless_stable_am1uc2_catalog.pdm_ops.work_orders_current

joins:
  - name: dim_station
    source: serverless_stable_am1uc2_catalog.pdm_raw.station_master
    "on": source.station_id = dim_station.station_id

comment: Maintenance work orders raised from live risk alerts in the Plant Health
  Live app.

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
    expr: CAST(source.created_at AS DATE)

measures:
  - name: Work Orders
    expr: COUNT(1)
    synonyms:
      - tickets
      - maintenance orders

  - name: Open Work Orders
    expr: "COUNT(1) FILTER (WHERE source.status IN ('open', 'in_progress'))"
    synonyms:
      - backlog

  - name: Completed Work Orders
    expr: COUNT(1) FILTER (WHERE source.status = 'completed')

  - name: Avg Risk At Creation
    expr: AVG(source.failure_probability)
    format:
      type: percentage

  - name: Avg Minutes To Complete
    expr: AVG((unix_seconds(source.completed_at) - unix_seconds(source.created_at))
      / 60.0) FILTER (WHERE source.status = 'completed')
$$
```

```python
display(spark.sql("""SELECT Plant, MEASURE(Failures) AS failures, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min,
                     MEASURE(`Preventive Share`) AS preventive_share, MEASURE(`Parts Cost USD`) AS parts_cost_usd
                     FROM pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY Plant"""))
display(spark.sql("""SELECT Plant, MEASURE(`Stations At High Risk`) AS high_risk_stations, MEASURE(`Avg Failure Probability`) AS avg_risk,
                     MEASURE(`Avg Sensor To Score Latency Seconds`) AS latency_s
                     FROM pdm_ops.station_risk_metrics WHERE `Score Time` > current_timestamp() - INTERVAL 10 MINUTES GROUP BY ALL ORDER BY Plant"""))
display(spark.sql("""SELECT Status, Priority, MEASURE(`Work Orders`) AS work_orders, MEASURE(`Avg Risk At Creation`) AS avg_risk_at_creation
                     FROM pdm_ops.work_order_metrics GROUP BY ALL"""))
```

Output:

| Plant | failures | mttr_min | preventive_share | parts_cost_usd |
|---|---|---|---|---|
| Plant East | 373 | 112.76728331661222 | 0.1806167400881057 | 2713614.1188870384 |
| Plant North | 340 | 111.91021343462346 | 0.2290249433106576 | 2518897.5788193042 |
| Plant South | 384 | 112.16677532169717 | 0.1812366737739872 | 2891611.356288852 |

Output:

| Plant | high_risk_stations | avg_risk | latency_s |
|---|---|---|---|
| Plant East | 5 | 0.05213801136363641 | 35.41061818181818 |
| Plant North | 3 | 0.052515852272727266 | 35.41061818181818 |
| Plant South | 9 | 0.10495880681818184 | 35.41061818181818 |

Output:

| Status | Priority | work_orders | avg_risk_at_creation |
|---|---|---|---|
| completed | P1 | 3 | 0.81130000 |
| completed | P2 | 1 | 0.98980000 |
