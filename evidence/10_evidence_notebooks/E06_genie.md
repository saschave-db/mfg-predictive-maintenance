# Executed notebook: E06_genie

Exported from Databricks job run `994447175034582` (task `E06_genie`, task run `886242903537339`).

Result: **SUCCESS** · start 2026-10-07T23:01:01.682000+00:00 · end 2026-10-07T23:05:25.536000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


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
data sources: ['pdm_core.station_health_current', 'pdm_ops.maintenance_metrics', 'pdm_ops.station_risk_metrics', 'pdm_ops.work_order_metrics', 'pdm_ops.work_orders_current']
sample questions: ['How many open work orders do we have by priority?', 'Why is the riskiest station at risk?', 'Which stations need maintenance soon?', 'Which station types fail most often and what is their MTTR?']
example SQL questions: ['How did average risk develop per plant over the last 15 minutes?', 'How many open work orders are there per plant?', 'Which stations are at high risk right now?', 'What is the MTTR and failure count by station type?']
benchmarks: 10

instructions:
You are a maintenance planning assistant for three plants (Plant North = PLT-N, Plant South = PLT-S, Plant East = PLT-E),
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
   "attachment_id": "01f1c2a300b41a879d43c9d4c57beb7d",
   "query": {
    "description": "You want to see a list of all stations that are currently at high risk of failure.",
    "query": "SELECT COUNT(*) AS `high_risk_stations`\nFROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`\nWHERE `risk_band` = 'HIGH'",
    "query_result_metadata": {
     "row_count": 1
    },
    "statement_id": "01f1c2a3-00be-1b07-9165-720eab466ddb",
    "thoughts": [
     {
      "content": "You want to see a list of all stations that are currently at high risk of failure.",
      "thought_type": "THOUGHT_TYPE_DESCRIPTION"
     },
     {
      "content": "- serverless_stable_am1uc2_catalog.pdm_core.station_health_current",
      "thought_type": "THOUGHT_TYPE_DATA_SOURCING"
     },
     {
      "content": "- Filter stations to include only those with a risk band labeled 'HIGH'.\n- Retrieve the station ID, plant ID, station type, and failure probability as a percentage for each high-risk station.\n- Also include the top signal causing the risk and the percentage deviation of that signal.\n- Order the results by failure probability in descending order to show the highest risk stations first.",
      "thought_type": "THOUGHT_TYPE_STEPS"
     }
    ]
   }
  },
  {
   "attachment_id": "01f1c2a3019d19b98562c96913dde14d",
   "suggested_questions": {
    "questions": [
     "What are the top signals causing high risk in stations right now?",
     "How many stations are at high risk in each plant currently?",
     "What is the average failure probability of stations at high risk right now?"
    ]
   }
  },
  {
   "text": {
    "content": "There are **4** stations at **HIGH** risk right now. Based on the current snapshot, the count of stations needing the most immediate maintenance attention is **4**."
   }
  }
 ],
 "content": "How many stations are at high risk right now?",
 "conversation_id": "01f1c2a2ff3f113bae3e0bae29a420c0",
 "created_timestamp": 1791414074921,
 "id": "01f1c2a2ff511c40bf196a3b19f9c227",
 "last_updated_timestamp": 1791414085088,
 "message_id": "01f1c2a2ff511c40bf196a3b19f9c227",
 "query_result": {
  "row_count": 1,
  "statement_id": "01f1c2a3-00be-1b07-9165-720eab466ddb"
 },
 "space_id": "01f1c10d662111078cd7326dff1774c6",
 "status": "COMPLETED",
 "user_id": 5511969577895513
}

### PASS (13.6 s): How many stations are at high risk right now?
Genie SQL:
SELECT COUNT(*) AS `high_risk_stations`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'HIGH'
Genie rows: [[4]]
Reference rows: [[4]]
Genie text: There are **4** stations at **HIGH** risk right now. Based on the current snapshot, the count of stations needing the most immediate maintenance attention is **4**.

### PASS (13.2 s): How many stations are currently down?
Genie SQL:
SELECT COUNT(*) AS `stations_currently_down`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'DOWN'
Genie rows: [[0]]
Reference rows: [[0]]
Genie text: There are **0** stations currently down, based on the current station status data. With **0** stations in the **DOWN** category, all stations are currently operating rather than stopped.

### PASS (18.9 s): What are the 5 stations with the highest failure probability right now?
Genie SQL:
WITH `ranked_stations` AS (
  SELECT
    `station_id`,
    `plant_id`,
    `line_id`,
    `station_type`,
    `failure_probability` * 100 AS `failure_probability_pct`,
    `risk_band`,
    `top_signal`,
    `top_signal_deviation_pct`,
    RANK() OVER (ORDER BY `failure_probability` DESC) AS `risk_rank`
  FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
  WHERE `failure_probability` IS NOT NULL
    AND `station_id` IS NOT NULL
)
SELECT
  `station_id`,
  `plant_id`,
  `line_id`,
  `station_type`,
  `failure_probability_pct`,
  `risk_band`,
  `top_signal`,
  `top_signal_deviation_pct`
FROM `ranked_stations`
WHERE `risk_rank` <= 5
ORDER BY `failure_probability_pct` DESC, `station_id` ASC
Genie rows: [['PLT-S-A06', 'PLT-S', 'PLT-S-A', 'cnc_mill', 99.63, 'HIGH', 'spindle_rpm', 29.6], ['PLT-S-D04', 'PLT-S', 'PLT-S-D', 'robot_arm', 98.9, 'HIGH', 'bearing_temp_c', 13.8], ['PLT-S-C02', 'PLT-S', 'PLT-S-C', 'cnc_mill', 88.53, 'HIGH', 'vibration_rms', 10.8], ['PLT-N-D08', 'PLT-N', 'PLT-N-D', 'press', 79.11, 'HIGH', 'acoustic_db', 10.1], ['PLT-S-D07', 'PLT-S', 'PLT-S-D', 'welder', 67.17999999999999, 'ELEVATED', 'vibration_rms', 14.9]]
Reference rows: [['PLT-S-A06'], ['PLT-S-D04'], ['PLT-S-C02'], ['PLT-N-D08'], ['PLT-S-D07']]
Genie text: The **5 stations with the highest failure probability right now** are:
- **PLT-S-A06** — **99.63%** (**HIGH**)
- **PLT-S-D04** — **98.9%** (**HIGH**)
- **PLT-S-C02** — **88.53%** (**HIGH**)
- **PLT-N-D08** — **79.11%** (**HIGH**)
- **PLT-S-D07** — **67.18%** (**ELEVATED**)

Of these 5 stations, **4 are in Plant South** and **4 are already in the HIGH risk band**, indicating the most urgent current

### PASS (12.1 s): Which station type had the most failures?
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
Genie text: The station type with the most failures is **cnc_mill**, with **296** failures. In the result shown, **cnc_mill** is the top-ranked station type for failures.

### PASS (13.3 s): What is the mean time to repair in minutes for each plant?
Genie SQL:
SELECT
  `Plant`,
  MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `Plant` ASC
Genie rows: [['Plant East', 112.76728331661222], ['Plant North', 111.91021343462346], ['Plant South', 112.16677532169717]]
Reference rows: [['Plant East', 112.76728331661222], ['Plant North', 111.91021343462346], ['Plant South', 112.16677532169717]]
Genie text: The mean time to repair is **112.77 minutes** for **Plant East**, **111.91 minutes** for **Plant North**, and **112.17 minutes** for **Plant South**. Across all 3 plants, repair times are very similar, with less than **1 minute** separating the highest and lowest values.

### PASS (17.6 s): Which failure mode caused the most downtime?
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
ORDER BY `downtime_minutes` DESC;
Genie rows: [['overheating', 56431.49725154227]]
Reference rows: [['overheating', 56431.49725154227]]
Genie text: The failure mode with the most downtime is **overheating**, with **56,431** downtime minutes. Based on the single result returned, **overheating** is the top downtime driver in the maintenance data.

### PASS (17.3 s): What is the total parts cost per plant?
Genie SQL:
SELECT `Plant`, MEASURE(`Parts Cost USD`) AS `parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `parts_cost_usd` DESC
Genie rows: [['Plant South', 2891611.356288852], ['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042]]
Reference rows: [['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042], ['Plant South', 2891611.356288852]]
Genie text: The total parts cost is highest for **Plant South** at **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across all 3 plants shown, **Plant South** has the highest total parts cost and **Plant North** the lowest.

### PASS (18.8 s): What share of repairs were preventive for each station type?
Genie SQL:
SELECT
  `Station Type`,
  MEASURE(`Preventive Share`) AS `preventive_share`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `preventive_share` DESC
Genie rows: [['welder', Decimal('0.2121212121212121')], ['press', Decimal('0.2112676056338028')], ['conveyor', Decimal('0.1842105263157895')], ['cnc_mill', Decimal('0.1828254847645429')], ['robot_arm', Decimal('0.1746987951807229')]]
Reference rows: [['cnc_mill', Decimal('0.1828254847645429')], ['conveyor', Decimal('0.1842105263157895')], ['press', Decimal('0.2112676056338028')], ['robot_arm', Decimal('0.1746987951807229')], ['welder', Decimal('0.2121212121212121')]]
Genie text: Preventive repairs made up **17.47% to 21.21%** of repairs across the 5 station types shown, with **welder** highest and **robot_arm** lowest.

- **welder:** **21.21%**
- **press:** **21.13%**
- **conveyor:** **18.42%**
- **cnc_mill:** **18.28%**
- **robot_arm:** **17.47%**

The spread is narrow, so preventive repair share appears fairly consistent by station type in this result.

### PASS (11.8 s): How many failures did Plant North have?
Genie SQL:
SELECT MEASURE(`Failures`) AS `failures`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` = 'Plant North'
GROUP BY ALL
Genie rows: [[340]]
Reference rows: [[340]]
Genie text: **Plant North** had **340 failures**. In this result, **340** is the total failure count returned for **Plant North**.

### PASS (17.5 s): List the stations on line PLT-S-B with their current risk band.
Genie SQL:
SELECT
  `station_id`,
  `risk_band`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `line_id` = 'PLT-S-B'
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `station_id` ASC
Genie rows: [['PLT-S-B01', 'NORMAL'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Reference rows: [['PLT-S-B01', 'NORMAL'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Genie text: All **8 stations** on line **PLT-S-B** are currently in the **NORMAL** risk band, with no elevated, high, or down stations shown.

Notable stations include:
- **PLT-S-B01** — **NORMAL**
- **PLT-S-B02** — **NORMAL**
- **PLT-S-B03** — **NORMAL**
- **PLT-S-B04** — **NORMAL**
- **PLT-S-B05** — **NORMAL**
```

```python
display(spark.createDataFrame(results, "verdict string, seconds double, question string"))
print(f"{sum(r[0] == 'PASS' for r in results)}/{len(results)} benchmark questions match the reference result")
```

Output:

| verdict | seconds | question |
|---|---|---|
| PASS | 13.6 | How many stations are at high risk right now? |
| PASS | 13.2 | How many stations are currently down? |
| PASS | 18.9 | What are the 5 stations with the highest failure probability right now? |
| PASS | 12.1 | Which station type had the most failures? |
| PASS | 13.3 | What is the mean time to repair in minutes for each plant? |
| PASS | 17.6 | Which failure mode caused the most downtime? |
| PASS | 17.3 | What is the total parts cost per plant? |
| PASS | 18.8 | What share of repairs were preventive for each station type? |
| PASS | 11.8 | How many failures did Plant North have? |
| PASS | 17.5 | List the stations on line PLT-S-B with their current risk band. |

Output:

```text
10/10 benchmark questions match the reference result
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
Genie text: **7 stations** currently need maintenance soon: **4 are HIGH risk** and **3 are ELEVATED**. Some of the highest-risk stations are:
- **PLT-S-C08** — **99.6%** risk (**HIGH**), driven by **vibration_rms**
- **PLT-S-D04** — **98.6%** risk (**HIGH**), driven by **bearing_temp_c**
- **PLT-N-C05** — **88.5%** risk (**HIGH**), driven by **vibration_rms**
- **PLT-S-C02** — **87.6%** risk (**HIGH**), driven by **motor_current_a**
- **PLT-N-C01** — **51.5%** risk (**ELEVATED**), driven by **vibration_rms**

Across these 7 stations, risk ranges from **47.6% to 99.6%**, and **Plant South** accounts for **4 of the 7** stations flagged for near-term maintenance.
Genie SQL:
SELECT station_health_current.station_id, station_health_current.plant_id, station_health_current.line_id, station_health_current.station_type, station_health_current.risk_band, ROUND(station_health_current.failure_probability * 100, 1) AS risk_pct, station_health_current.top_signal, station_health_current.top_signal_deviation_pct
FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
WHERE station_health_current.risk_band IN ('HIGH', 'ELEVATED')
  AND station_health_current.failure_probability IS NOT NULL
ORDER BY station_health_current.failure_probability DESC, station_health_current.station_id ASC
rows: [['PLT-S-C08', 'PLT-S', 'PLT-S-C', 'press', 'HIGH', 99.9, 'vibration_rms', 29.9], ['PLT-S-D04', 'PLT-S', 'PLT-S-D', 'robot_arm', 'HIGH', 99.5, 'bearing_temp_c', 41.6], ['PLT-N-C05', 'PLT-N', 'PLT-N-C', 'conveyor', 'HIGH', 91.8, 'vibration_rms', 75.9], ['PLT-S-C02', 'PLT-S', 'PLT-S-C', 'cnc_mill', 'HIGH', 76.9, 'motor_current_a', 10.9], ['PLT-N-D03', 'PLT-N', 'PLT-N-D', 'welder', 'ELEVATED', 54.4, 'vibration_rms', 34.1]]

### Why is the riskiest station at risk?
Genie text: The riskiest station is **PLT-S-C08** in plant **PLT-S** on line **PLT-S-C**, with a failure probability of **99.91%** and a risk band of **HIGH**. Station **PLT-S-C08** is at risk because the top signal is **vibration_rms**, which is running **28.7%** above normal; the station type is **press**.
Genie SQL:
WITH ranked AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    failure_probability * 100 AS risk_pct,
    risk_band,
    top_signal,
    top_signal_deviation_pct,
    RANK() OVER (ORDER BY failure_probability DESC) AS risk_rank
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE failure_probability IS NOT NULL AND top_signal IS NOT NULL AND top_signal_deviation_pct IS NOT NULL
)
SELECT
  station_id,
  plant_id,
  line_id,
  station_type,
  risk_pct,
  risk_band,
  top_signal,
  top_signal_deviation_pct
FROM ranked
WHERE risk_rank = 1
ORDER BY station_id ASC
rows: [['PLT-S-C08', 'PLT-S', 'PLT-S-C', 'press', 99.95, 'HIGH', 'vibration_rms', 27.7]]

### Which station types fail most often and what is their MTTR?
Genie text: The station type that fails most often is **cnc_mill** with **296** failures and an average repair time of **115.2 minutes**. Examples include:
- **cnc_mill** — **296** failures, **115.2 minutes** MTTR
- **press** — **280** failures, **110.8 minutes** MTTR
- **welder** — **260** failures, **112.5 minutes** MTTR
- **robot_arm** — **137** failures, **108.9 minutes** MTTR
- **conveyor** — **124** failures, **112.0 minutes** MTTR
Across these 5 station types, failures drop sharply after the top three, while MTTR stays fairly consistent at about **109 to 115 minutes**.
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
Genie text: There are **0** open work orders in the visible results for both priorities returned: **P1** and **P2**. Across these **2** priority levels shown, open work orders are **zero in every case**.

- **P1:** **0** open work orders
- **P2:** **0** open work orders
Genie SQL:
SELECT `Priority`, MEASURE(`Open Work Orders`) AS `open_work_orders`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_order_metrics`
WHERE `Priority` IS NOT NULL
GROUP BY ALL
ORDER BY `open_work_orders` DESC
rows: [['P1', 0], ['P2', 0]]
```
