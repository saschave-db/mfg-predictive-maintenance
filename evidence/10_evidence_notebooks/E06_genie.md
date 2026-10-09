# Executed notebook: E06_genie

Exported from Databricks job run `704920341411517` (task `E06_genie`, task run `559327244084078`).

Result: **SUCCESS** · start 2026-10-09T16:56:40.525000+00:00 · end 2026-10-09T17:02:40.189000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/704920341411517


# E06 · Genie agent on metric views and work orders

**What was built.** Genie agent "Plant Maintenance Agent", defined as code in `src/genie/space_config.py`:
3 metric views + `station_health_current` + `work_orders_current`, text instructions (plant naming, risk bands,
compressed time, where to find what), 4 example SQL queries, 4 sample questions and 10 benchmark questions with
reference SQL. Deployed with `tools/genie_deploy.py`.

**What this notebook proves.** The deployed configuration, and live answers: each benchmark question is asked through
the Genie Conversation API; Genie's generated SQL and the reference SQL are executed back to back and compared.

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
import sys, os, time, json
sys.path.append(os.path.abspath("../.."))
from genie import space_config as cfg
```

## 1 · Deployed configuration

```python
sp = w.api_client.do("GET", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}", query={"include_serialized_space": "true"})
ser = json.loads(sp["serialized_space"])
print("title:", sp["title"], "| warehouse:", sp["warehouse_id"])
print("data sources:", [t["identifier"].split(".", 1)[1] for k in ("tables", "metric_views") for t in ser["data_sources"].get(k, [])])
print("sample questions:", [q["question"][0] for q in ser["config"]["sample_questions"]])
print("example SQL questions:", [q["question"][0] for q in ser["instructions"]["example_question_sqls"]])
print("benchmarks:", len(ser["benchmarks"]["questions"]))
print("\ninstructions:\n" + ser["instructions"]["text_instructions"][0]["content"][0])
```

Output:

```text
title: Plant Maintenance Agent | warehouse: fb9bc265e9f4578a
data sources: ['pdm_core.station_health_current', 'pdm_ops.maintenance_metrics', 'pdm_ops.oem_delivery_exposure', 'pdm_ops.station_risk_metrics', 'pdm_ops.work_order_metrics', 'pdm_ops.work_orders_current']
sample questions: ['How many open work orders do we have by priority?', 'Which OEM programs are exposed to a line stop right now?', 'Why is the riskiest station at risk?', 'Which stations need maintenance soon?', 'Which station types fail most often and what is their MTTR?']
example SQL questions: ['How did average risk develop per plant over the last 15 minutes?', 'Which OEM customer has the highest delivery exposure right now?', 'How many open work orders are there per plant?', 'Which stations are at high risk right now?', 'What is the MTTR and failure count by station type?']
benchmarks: 12

instructions:
You are a maintenance planning assistant for Volta Industrial, a Tier-1 supplier of aluminum EV battery enclosures.
```

## 2 · Live benchmark: Genie answer vs reference SQL

```python
def norm(rows):
    out = []
    for r in rows:
        vals = set()
        for v in r:
            try:
                vals.add(round(float(v), 2))
            except (TypeError, ValueError):
                vals.add(None if v is None else str(v))
        out.append(vals)
    return out


results, raw_shown = [], False
for q, ref_sql in cfg.benchmarks(CATALOG):
    t0 = time.time()
    msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q)
    secs = time.time() - t0
    if not raw_shown:  # one complete raw API response, as returned by the Genie Conversation API
        print("RAW Genie message response:\n" + json.dumps(msg.as_dict(), indent=1, default=str)[:4000])
        raw_shown = True
    sql = next((a.query.query for a in (msg.attachments or []) if a.query), None)
    text = next((a.text.content for a in (msg.attachments or []) if a.text and a.text.content), None)
    g_rows = [list(r) for r in spark.sql(sql).collect()] if sql else []
    r_rows = [list(r) for r in spark.sql(ref_sql).collect()]
    ok = bool(sql) and len(g_rows) == len(r_rows) and all(any(rr <= gg for gg in norm(g_rows)) for rr in norm(r_rows))
    results.append((("PASS" if ok else "FAIL"), round(secs, 1), q))
    print(f"\n### {'PASS' if ok else 'FAIL'} ({secs:.1f} s): {q}")
    print("Genie SQL:\n" + (sql or "<none>"))
    print("Genie rows:", g_rows[:5])
    print("Reference rows:", r_rows[:5])
    if text:
        print("Genie text:", text[:400])
```

Output:

```text
RAW Genie message response:
{
 "attachments": [
  {
   "attachment_id": "01f1c40273e91b298346a7ce6e49f239",
   "query": {
    "description": "You want to see a list of all stations that are currently at high risk of failure, including details like their ID, plant location, type, risk percentage, and the main reason for the risk.",
    "query": "SELECT COUNT(*) AS `high_risk_stations`\nFROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`\nWHERE `risk_band` = 'HIGH'",
    "query_result_metadata": {
     "row_count": 1
    },
    "statement_id": "01f1c402-73f9-1fde-b816-21ae3a637308",
    "thoughts": [
     {
      "content": "You want to see a list of all stations that are currently at high risk of failure, including details like their ID, plant location, type, risk percentage, and the main reason for the risk.",
      "thought_type": "THOUGHT_TYPE_DESCRIPTION"
     },
     {
      "content": "- serverless_stable_am1uc2_catalog.pdm_core.station_health_current",
      "thought_type": "THOUGHT_TYPE_DATA_SOURCING"
     },
     {
      "content": "- Filter stations to only those currently classified as 'HIGH' risk band.\n- Retrieve station ID, plant ID, station type, failure probability as a percentage, top signal causing the risk, and the deviation percentage of that signal.\n- Order the results by failure probability in descending order to show the riskiest stations first.",
      "thought_type": "THOUGHT_TYPE_STEPS"
     }
    ]
   }
  },
  {
   "text": {
    "content": "There are **2** stations at **HIGH** risk right now. Based on the current station snapshot, the count of stations with risk band = **HIGH** is **2**."
   }
  },
  {
   "attachment_id": "01f1c402767b13a1af3bf96d325670d9",
   "suggested_questions": {
    "questions": [
     "What are the top signals causing high risk at the stations?",
     "How many stations are at elevated risk right now?",
     "What is the distribution of high risk stations by plant?"
    ]
   }
  }
 ],
 "content": "How many stations are at high risk right now?",
 "conversation_id": "01f1c4027293192889961efc2e5f1860",
 "created_timestamp": 1791565021802,
 "id": "01f1c40272ab1e99b1c787dd36b922cf",
 "last_updated_timestamp": 1791565029789,
 "message_id": "01f1c40272ab1e99b1c787dd36b922cf",
 "query_result": {
  "row_count": 1,
  "statement_id": "01f1c402-73f9-1fde-b816-21ae3a637308"
 },
 "space_id": "01f1c10d662111078cd7326dff1774c6",
 "status": "COMPLETED",
 "user_id": 5511969577895513
}

### PASS (12.7 s): How many stations are at high risk right now?
Genie SQL:
SELECT COUNT(*) AS `high_risk_stations`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'HIGH'
Genie rows: [[2]]
Reference rows: [[2]]
Genie text: There are **2** stations at **HIGH** risk right now. Based on the current station snapshot, the count of stations with risk band = **HIGH** is **2**.

### PASS (13.0 s): How many stations are currently down?
Genie SQL:
SELECT COUNT(*) AS `stations_currently_down`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'DOWN'
Genie rows: [[0]]
Reference rows: [[0]]
Genie text: There are **0** stations currently down, based on `risk_band = 'DOWN'` in `pdm_core.station_health_current`. This means no stations are currently reported as stopped.

### PASS (18.3 s): What are the 5 stations with the highest failure probability right now?
Genie SQL:
WITH `ranked_stations` AS (
  SELECT
    `station_id`,
    `plant_id`,
    `line_id`,
    `station_type`,
    `risk_band`,
    `top_signal`,
    `failure_probability` * 100 AS `failure_probability_pct`,
    RANK() OVER (ORDER BY `failure_probability` DESC) AS `rank`
  FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
  WHERE `failure_probability` IS NOT NULL
    AND `station_id` IS NOT NULL
)
SELECT
  `station_id`,
  `plant_id`,
  `line_id`,
  `station_type`,
  `risk_band`,
  `top_signal`,
  `failure_probability_pct`
FROM `ranked_stations`
WHERE `rank` <= 5
ORDER BY `failure_probability_pct` DESC, `station_id` ASC
Genie rows: [['PLT-N-C01', 'PLT-N', 'PLT-N-C', 'press', 'HIGH', 'hydraulic_pressure_bar', 99.9], ['PLT-S-B01', 'PLT-S', 'PLT-S-B', 'press', 'HIGH', 'motor_current_a', 99.72999999999999], ['PLT-E-D07', 'PLT-E', 'PLT-E-D', 'welder', 'ELEVATED', 'cycle_time_s', 51.449999999999996], ['PLT-E-A02', 'PLT-E', 'PLT-E-A', 'cnc_mill', 'ELEVATED', 'motor_current_a', 48.39], ['PLT-S-C02', 'PLT-S', 'PLT-S-C', 'cnc_mill', 'NORMAL', 'vibration_rms', 25.28]]
Reference rows: [['PLT-N-C01'], ['PLT-S-B01'], ['PLT-E-D07'], ['PLT-E-A02'], ['PLT-S-C02']]
Genie text: The **5 stations with the highest failure probability right now** are:
- **PLT-N-C01** (Plant **PLT-N**) — **99.9%** failure probability, **HIGH** risk, top signal: **hydraulic_pressure_bar**
- **PLT-S-B01** (Plant **PLT-S**) — **99.73%** failure probability, **HIGH** risk, top signal: **motor_current_a**
- **PLT-E-D07** (Plant **PLT-E**) — **51.45%** failure probability, **ELEVATED** risk, top si

### PASS (18.4 s): Which station type had the most failures?
Genie SQL:
WITH `ranked_station_types` AS (
  SELECT
    `Station Type`,
    MEASURE(`Failures`) AS `failures`,
    RANK() OVER (ORDER BY MEASURE(`Failures`) DESC) AS `failure_rank`
  FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
  WHERE `Station Type` IS NOT NULL
  GROUP BY ALL
)
SELECT
  `Station Type`,
  `failures`
FROM `ranked_station_types`
WHERE `failure_rank` <= 1
ORDER BY `failure_rank` ASC, `Station Type` ASC;
Genie rows: [['cnc_mill', 296]]
Reference rows: [['cnc_mill', 296]]
Genie text: The station type with the most failures is **cnc_mill**, with **296 failures**. Based on the result shown, **cnc_mill** ranks highest for failures among station types.

### PASS (12.6 s): What is the mean time to repair in minutes for each plant?
Genie SQL:
SELECT `Plant`, MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `mttr_minutes` DESC
Genie rows: [['Plant East', 112.76728331661222], ['Plant South', 112.16677532169717], ['Plant North', 111.91021343462346]]
Reference rows: [['Plant East', 112.76728331661222], ['Plant North', 111.91021343462346], ['Plant South', 112.16677532169717]]
Genie text: The mean time to repair is **112.77 minutes** for **Plant East**, **112.17 minutes** for **Plant South**, and **111.91 minutes** for **Plant North**. Across all 3 plants, repair times are very similar, with **Plant East** the highest and **Plant North** the lowest.

### PASS (18.4 s): Which failure mode caused the most downtime?
Genie SQL:
WITH `ranked_failure_modes` AS (
  SELECT
    `Failure Mode`,
    MEASURE(`Downtime Minutes`) AS `downtime_minutes`,
    RANK() OVER (ORDER BY MEASURE(`Downtime Minutes`) DESC) AS `downtime_rank`
  FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
  WHERE `Failure Mode` IS NOT NULL
  GROUP BY ALL
)
SELECT
  `Failure Mode`,
  `downtime_minutes`
FROM `ranked_failure_modes`
WHERE `downtime_rank` <= 1
ORDER BY `downtime_rank` ASC, `Failure Mode` ASC;
Genie rows: [['overheating', 56431.49725154227]]
Reference rows: [['overheating', 56431.49725154227]]
Genie text: The failure mode that caused the most downtime was **overheating**, with **56,431** downtime minutes. Based on the result shown, **overheating** is the top downtime driver across the failure modes included in the query.

### PASS (12.2 s): What is the total parts cost per plant?
Genie SQL:
SELECT `Plant`, MEASURE(`Parts Cost USD`) AS `parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `parts_cost_usd` DESC
Genie rows: [['Plant South', 2891611.356288852], ['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042]]
Reference rows: [['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042], ['Plant South', 2891611.356288852]]
Genie text: Total parts cost is highest at **Plant South** with **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across the 3 plants shown, **Plant South** has the highest total parts cost and **Plant North** the lowest.

### PASS (13.6 s): What share of repairs were preventive for each station type?
Genie SQL:
SELECT
  `Station Type`,
  MEASURE(`Preventive Share`) AS `preventive_share`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `Station Type` ASC
Genie rows: [['cnc_mill', Decimal('0.1828254847645429')], ['conveyor', Decimal('0.1842105263157895')], ['press', Decimal('0.2112676056338028')], ['robot_arm', Decimal('0.1746987951807229')], ['welder', Decimal('0.2121212121212121')]]
Reference rows: [['cnc_mill', Decimal('0.1828254847645429')], ['conveyor', Decimal('0.1842105263157895')], ['press', Decimal('0.2112676056338028')], ['robot_arm', Decimal('0.1746987951807229')], ['welder', Decimal('0.2121212121212121')]]
Genie text: Preventive repairs ranged from **17.47%** to **21.21%** across the 5 station types shown.  
- **cnc_mill:** **18.28%**
- **conveyor:** **18.42%**
- **press:** **21.13%**
- **robot_arm:** **17.47%**
- **welder:** **21.21%**

Among these station types, **welder** had the highest preventive share and **robot_arm** had the lowest.

### PASS (12.2 s): How many failures did Plant North have?
Genie SQL:
SELECT MEASURE(`Failures`) AS `total_failures`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` = 'Plant North'
GROUP BY ALL
Genie rows: [[340]]
Reference rows: [[340]]
Genie text: Plant North had **340 failures**.

### PASS (18.1 s): List the stations on line PLT-S-B with their current risk band.
Genie SQL:
SELECT `station_id`, `risk_band`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `line_id` = 'PLT-S-B'
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `station_id` ASC
Genie rows: [['PLT-S-B01', 'HIGH'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Reference rows: [['PLT-S-B01', 'HIGH'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Genie text: There are **8 stations** on line **PLT-S-B**; **PLT-S-B01** is **HIGH** risk, and the other **7 stations** are **NORMAL**.

Examples include:
- **PLT-S-B01** — **HIGH**
- **PLT-S-B02** — **NORMAL**
- **PLT-S-B03** — **NORMAL**
- **PLT-S-B04** — **NORMAL**
- **PLT-S-B05** — **NORMAL**

This line is mostly stable right now, with only **one station** currently above normal risk.

### PASS (18.5 s): Which line has the highest risk-weighted OEM delivery exposure right now, and which OEM program does it supply?
Genie SQL:
WITH ranked AS (
  SELECT
    line_id,
    plant_id,
    oem_customer,
    vehicle_program,
    risk_weighted_exposure_usd,
    RANK() OVER (ORDER BY risk_weighted_exposure_usd DESC) AS rank
  FROM serverless_stable_am1uc2_catalog.pdm_ops.oem_delivery_exposure
  WHERE line_id IS NOT NULL AND risk_weighted_exposure_usd IS NOT NULL
)
SELECT line_id, plant_id, oem_customer, vehicle_program, risk_weighted_exposure_usd
FROM ranked
WHERE rank = 1
Genie rows: [['PLT-S-B', 'PLT-S', 'Fjord Electric', 'FE Pace Sedan', 912604.0]]
Reference rows: [['PLT-S-B', 'FE Pace Sedan']]
Genie text: The line with the highest risk-weighted OEM delivery exposure right now is **PLT-S-B** at plant **PLT-S**, with **$912,604.0** in risk-weighted exposure. Line **PLT-S-B** supplies OEM customer **Fjord Electric** for vehicle program **FE Pace Sedan**.

### PASS (18.0 s): What is the JIS buffer in minutes for each line supplying Nordvik Motors?
Genie SQL:
SELECT pdm_ops_oem_delivery_exposure.line_id, pdm_ops_oem_delivery_exposure.plant_id, pdm_ops_oem_delivery_exposure.jis_buffer_min
FROM serverless_stable_am1uc2_catalog.pdm_ops.oem_delivery_exposure AS pdm_ops_oem_delivery_exposure
WHERE pdm_ops_oem_delivery_exposure.oem_customer = 'Nordvik Motors'
  AND pdm_ops_oem_delivery_exposure.line_id IS NOT NULL
  AND pdm_ops_oem_delivery_exposure.jis_buffer_min IS NOT NULL
ORDER BY pdm_ops_oem_delivery_exposure.line_id ASC
Genie rows: [['PLT-E-D', 'PLT-E', 90], ['PLT-N-A', 'PLT-N', 60], ['PLT-N-B', 'PLT-N', 75], ['PLT-N-C', 'PLT-N', 60]]
Reference rows: [['PLT-E-D', 90], ['PLT-N-A', 60], ['PLT-N-B', 75], ['PLT-N-C', 60]]
Genie text: Nordvik Motors has **4** supplying lines in the visible data, with JIS buffers ranging from **60 to 90 minutes**.

- **PLT-E-D** (Plant East): **90 minutes**
- **PLT-N-A** (Plant North): **60 minutes**
- **PLT-N-B** (Plant North): **75 minutes**
- **PLT-N-C** (Plant North): **60 minutes**
```

```python
display(spark.createDataFrame(results, "verdict string, seconds double, question string"))
print(f"{sum(r[0] == 'PASS' for r in results)}/{len(results)} benchmark questions match the reference result")
```

Output:

| verdict | seconds | question |
|---|---|---|
| PASS | 12.7 | How many stations are at high risk right now? |
| PASS | 13.0 | How many stations are currently down? |
| PASS | 18.3 | What are the 5 stations with the highest failure probability right now? |
| PASS | 18.4 | Which station type had the most failures? |
| PASS | 12.6 | What is the mean time to repair in minutes for each plant? |
| PASS | 18.4 | Which failure mode caused the most downtime? |
| PASS | 12.2 | What is the total parts cost per plant? |
| PASS | 13.6 | What share of repairs were preventive for each station type? |
| PASS | 12.2 | How many failures did Plant North have? |
| PASS | 18.1 | List the stations on line PLT-S-B with their current risk band. |
| PASS | 18.5 | Which line has the highest risk-weighted OEM delivery exposure right now, and which OEM program does it supply? |
| PASS | 18.0 | What is the JIS buffer in minutes for each line supplying Nordvik Motors? |

Output:

```text
12/12 benchmark questions match the reference result
```

## 3 · Sample questions (free-form answers)

```python
for q in cfg.SAMPLE_QUESTIONS:
    msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q)
    sql = next((a.query.query for a in (msg.attachments or []) if a.query), None)
    text = next((a.text.content for a in (msg.attachments or []) if a.text and a.text.content), None)
    print(f"\n### {q}\nGenie text: {text}\nGenie SQL:\n{sql}")
    if sql:
        print("rows:", [list(r) for r in spark.sql(sql).limit(5).collect()])
```

Output:

```text
### Which stations need maintenance soon?
Genie text: **4 stations** currently need maintenance soon based on elevated or high risk. The most urgent are **PLT-N-C01** at **99.9%** and **PLT-S-B01** at **99.73%** maintenance probability, while **PLT-E-D07** is at **51.45%** and **PLT-E-A02** is at **48.39%**. The two highest-risk stations are both **presses** in the **HIGH** band, while the two Plant East stations are in the **ELEVATED** band.
Genie SQL:
SELECT `station_id`, `plant_id`, `line_id`, `station_type`, `risk_band`, `failure_probability` * 100 AS `maintenance_probability_pct`, `top_signal`, `top_signal_deviation_pct`, `last_reading_ts` FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current` WHERE `station_id` IS NOT NULL AND `failure_probability` IS NOT NULL AND `risk_band` IN ('HIGH', 'ELEVATED') ORDER BY `failure_probability` DESC, `station_id` ASC
rows: [['PLT-N-C01', 'PLT-N', 'PLT-N-C', 'press', 'HIGH', 99.9, 'hydraulic_pressure_bar', 11.0, datetime.datetime(2026, 10, 7, 23, 44, 9)], ['PLT-S-B01', 'PLT-S', 'PLT-S-B', 'press', 'HIGH', 99.72999999999999, 'motor_current_a', 13.6, datetime.datetime(2026, 10, 7, 23, 44, 9)], ['PLT-E-D07', 'PLT-E', 'PLT-E-D', 'welder', 'ELEVATED', 51.449999999999996, 'cycle_time_s', 13.0, datetime.datetime(2026, 10, 7, 23, 44, 9)], ['PLT-E-A02', 'PLT-E', 'PLT-E-A', 'cnc_mill', 'ELEVATED', 48.39, 'motor_current_a', 9.4, datetime.datetime(2026, 10, 7, 23, 44, 9)]]

### Why is the riskiest station at risk?
Genie text: The riskiest station is **PLT-N-C01** in **PLT-N-C**, and **PLT-N-C01** is at risk because the top warning signal is **hydraulic_pressure_bar**, which is running **11.0%** away from normal. **PLT-N-C01** is a **press** station with **99.9%** failure probability and a **HIGH** risk band, which makes the hydraulic pressure issue the clearest visible driver of the current risk.
Genie SQL:
WITH ranked AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    failure_probability,
    risk_band,
    top_signal,
    top_signal_deviation_pct,
    RANK() OVER (ORDER BY failure_probability DESC) AS risk_rank
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE failure_probability IS NOT NULL
    AND top_signal IS NOT NULL
    AND top_signal_deviation_pct IS NOT NULL
)
SELECT
  station_id,
  plant_id,
  line_id,
  station_type,
  risk_band,
  ROUND(failure_probability * 100, 1) AS risk_pct,
  top_signal,
  top_signal_deviation_pct
FROM ranked
WHERE risk_rank = 1
ORDER BY station_id ASC
rows: [['PLT-N-C01', 'PLT-N', 'PLT-N-C', 'press', 'HIGH', 99.9, 'hydraulic_pressure_bar', 11.0]]

### Which station types fail most often and what is their MTTR?
Genie text: The station type with the most failures is **cnc_mill** with **296** failures and an average repair time of **115.2 minutes**. Examples include:
- **cnc_mill** — **296** failures, **115.2 min** MTTR
- **press** — **280** failures, **110.8 min** MTTR
- **welder** — **260** failures, **112.5 min** MTTR
- **robot_arm** — **137** failures, **108.9 min** MTTR
- **conveyor** — **124** failures, **112.0 min** MTTR
Across these 5 station types, MTTR is fairly consistent at about **109 to 115 minutes**, so the biggest difference is failure frequency rather than repair duration.
Genie SQL:
SELECT
  `Station Type`,
  MEASURE(`Failures`) AS `failures`,
  MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `failures` DESC
rows: [['cnc_mill', 296, 115.1976376037942], ['press', 280, 110.83746264557489], ['welder', 260, 112.50394617635841], ['robot_arm', 137, 108.85064914589415], ['conveyor', 124, 112.01279122873008]]

### How many open work orders do we have by priority?
Genie text: There are **0 open work orders** in the visible results for both priorities returned: **P1** and **P2**. In this result set, open work orders are **zero across all shown priorities**, so there is no higher-priority backlog visible.
Genie SQL:
SELECT
  `Priority`,
  MEASURE(`Open Work Orders`) AS `open_work_orders`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_order_metrics`
WHERE `Priority` IS NOT NULL
GROUP BY ALL
ORDER BY `open_work_orders` DESC
rows: [['P1', 0], ['P2', 0]]

### Which OEM programs are exposed to a line stop right now?
Genie text: There are **12 exposed OEM program-line combinations right now** with non-zero potential line-stop impact. Notable data points include:
- **Fjord Electric – FE Pace Sedan** at **PLT-S-B**: **$912,604** risk-weighted exposure, **HIGH** risk, **99.73%** failure probability, **51 minutes** of line-stop impact if the station fails
- **Nordvik Motors – NV-e5 Crossover** at **PLT-N-C**: **$609,440** risk-weighted exposure, **HIGH** risk, **99.9%** failure probability, **51 minutes** of line-stop impact
- **Aurora Elbil – Aurora A3 Hatch** at **PLT-E-A**: **$293,812** risk-weighted exposure, **ELEVATED** risk, **48.39%** failure probability, **55 minutes** of line-stop impact
- **Aurora Elbil – Aurora X5 SUV** at **PLT-E-C**: **$128,110** risk-weighted exposure, **NORMAL** risk, **12.54%** failure probability, **64 minutes** of line-stop impact
- **Nordvik Motors – NV-e5 Crossover** at **PLT-E-D**: **$104,205** risk-weighted exposure, **ELEVATED** risk, **51.45%** failure probability, **23 minutes** of line-stop impact

The highest current exposure is **Fjord Electric’s FE Pace Sedan on PLT-S-B**, and the 12 exposed combinations span all three OEMs and all three plants.
Genie SQL:
SELECT `oem_customer`, `vehicle_program`, `plant_id`, `line_id`, `riskiest_station_id`, `riskiest_risk_band`, `riskiest_failure_probability`, `oem_line_stop_min_if_fails`, `exposure_usd_if_fails`, `risk_weighted_exposure_usd` FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`oem_delivery_exposure` WHERE `oem_line_stop_min_if_fails` IS NOT NULL AND `oem_line_stop_min_if_fails` > 0 AND `risk_weighted_exposure_usd` IS NOT NULL ORDER BY `risk_weighted_exposure_usd` DESC, `exposure_usd_if_fails` DESC, `oem_customer` ASC, `vehicle_program` ASC
rows: [['Fjord Electric', 'FE Pace Sedan', 'PLT-S', 'PLT-S-B', 'PLT-S-B01', 'HIGH', 0.9973, 51.0, 915074.0, 912604.0], ['Nordvik Motors', 'NV-e5 Crossover', 'PLT-N', 'PLT-N-C', 'PLT-N-C01', 'HIGH', 0.999, 51.0, 610050.0, 609440.0], ['Aurora Elbil', 'Aurora A3 Hatch', 'PLT-E', 'PLT-E-A', 'PLT-E-A02', 'ELEVATED', 0.4839, 55.0, 607174.0, 293812.0], ['Aurora Elbil', 'Aurora X5 SUV', 'PLT-E', 'PLT-E-C', 'PLT-E-C04', 'NORMAL', 0.1254, 64.0, 1021610.0, 128110.0], ['Nordvik Motors', 'NV-e5 Crossover', 'PLT-E', 'PLT-E-D', 'PLT-E-D07', 'ELEVATED', 0.5145, 23.0, 202536.0, 104205.0]]
```
