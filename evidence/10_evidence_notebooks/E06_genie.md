# Executed notebook: E06_genie

Exported from Databricks job run `980301348000608` (task `E06_genie`, task run `1027823489205687`).

Result: **SUCCESS** · start 2026-10-06T17:46:32.647000+00:00 · end 2026-10-06T17:51:19.737000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


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


results = []
for q, ref_sql in cfg.benchmarks(CATALOG):
    t0 = time.time()
    msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q)
    secs = time.time() - t0
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
### PASS (18.0 s): How many stations are at high risk right now?
Genie SQL:
SELECT COUNT(*) AS `high_risk_stations`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'HIGH'
Genie rows: [[1]]
Reference rows: [[1]]
Genie text: There are **1** stations at **HIGH** risk right now based on `pdm_core.station_health_current`. This means the current count of stations in the **HIGH** risk band is **1**.

### PASS (17.7 s): How many stations are currently down?
Genie SQL:
SELECT COUNT(*) AS `stations_down`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'DOWN'
Genie rows: [[0]]
Reference rows: [[0]]
Genie text: There are **0 stations** currently marked as **DOWN**. Based on the current station status data, **no stations are currently down**.

### PASS (23.4 s): What are the 5 stations with the highest failure probability right now?
Genie SQL:
WITH ranked AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    ROUND(failure_probability * 100, 1) AS failure_probability_pct,
    risk_band,
    top_signal,
    RANK() OVER (ORDER BY failure_probability DESC) AS rank
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE failure_probability IS NOT NULL AND station_id IS NOT NULL
)
SELECT
  station_id,
  plant_id,
  line_id,
  station_type,
  failure_probability_pct,
  risk_band,
  top_signal
FROM ranked
WHERE rank <= 5
ORDER BY failure_probability_pct DESC, station_id ASC
Genie rows: [['PLT-E-B02', 'PLT-E', 'PLT-E-B', 'cnc_mill', 100.0, 'HIGH', 'bearing_temp_c'], ['PLT-S-C04', 'PLT-S', 'PLT-S-C', 'robot_arm', 67.8, 'ELEVATED', 'vibration_rms'], ['PLT-S-C01', 'PLT-S', 'PLT-S-C', 'press', 50.3, 'ELEVATED', 'vibration_rms'], ['PLT-N-D07', 'PLT-N', 'PLT-N-D', 'welder', 28.5, 'NORMAL', 'motor_current_a'], ['PLT-S-C02', 'PLT-S', 'PLT-S-C', 'cnc_mill', 26.1, 'NORMAL', 'vibration_rms']]
Reference rows: [['PLT-E-B02'], ['PLT-S-C04'], ['PLT-S-C01'], ['PLT-N-D07'], ['PLT-S-C02']]
Genie text: Would you prefer to see the top 5 stations by highest risk band instead of failure probability?

### PASS (18.1 s): Which station type had the most failures?
Genie SQL:
WITH ranked_station_types AS (
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
FROM ranked_station_types
WHERE `failure_rank` <= 1
ORDER BY `failure_rank` ASC, `Station Type` ASC;
Genie rows: [['cnc_mill', 296]]
Reference rows: [['cnc_mill', 296]]
Genie text: The station type with the most failures is **cnc_mill**, with **296** failures. Based on the result shown, **cnc_mill** ranks highest for failures among station types.

### PASS (12.8 s): What is the mean time to repair in minutes for each plant?
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

### PASS (19.1 s): Which failure mode caused the most downtime?
Genie SQL:
WITH ranked_failure_modes AS (
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
FROM ranked_failure_modes
WHERE `downtime_rank` <= 1
ORDER BY `downtime_minutes` DESC
Genie rows: [['overheating', 56431.49725154227]]
Reference rows: [['overheating', 56431.49725154227]]
Genie text: The failure mode that caused the most downtime was **overheating**, with **56,431** downtime minutes. In this result, **overheating** is the top downtime driver.

### PASS (12.1 s): What is the total parts cost per plant?
Genie SQL:
SELECT
  `Plant`,
  MEASURE(`Parts Cost USD`) AS `parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `parts_cost_usd` DESC
Genie rows: [['Plant South', 2891611.356288852], ['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042]]
Reference rows: [['Plant East', 2713614.1188870384], ['Plant North', 2518897.5788193042], ['Plant South', 2891611.356288852]]
Genie text: The total parts cost is highest for **Plant South** at **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across the 3 plants shown, **Plant South** has the highest total parts cost and **Plant North** the lowest.

### PASS (19.0 s): What share of repairs were preventive for each station type?
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
Genie text: Preventive repairs accounted for **21.21%** of work for **welder** stations, **21.13%** for **press**, **18.42%** for **conveyor**, **18.28%** for **cnc_mill**, and **17.47%** for **robot_arm**. Across these 5 station types, the preventive share is fairly close overall, ranging from **17.47%** to **21.21%**, with **welder** the highest and **robot_arm** the lowest.

### PASS (12.3 s): How many failures did Plant North have?
Genie SQL:
SELECT MEASURE(`Failures`) AS `failures`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` = 'Plant North'
GROUP BY ALL
Genie rows: [[340]]
Reference rows: [[340]]
Genie text: **Plant North** had **340 failures**. Based on the single result shown, the total failures for **Plant North** in this query is **340**.

### PASS (18.0 s): List the stations on line PLT-S-B with their current risk band.
Genie SQL:
SELECT station_id, risk_band
FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
WHERE line_id = 'PLT-S-B' AND station_id IS NOT NULL AND risk_band IS NOT NULL
ORDER BY station_id ASC
Genie rows: [['PLT-S-B01', 'HIGH'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Reference rows: [['PLT-S-B01', 'HIGH'], ['PLT-S-B02', 'NORMAL'], ['PLT-S-B03', 'NORMAL'], ['PLT-S-B04', 'NORMAL'], ['PLT-S-B05', 'NORMAL']]
Genie text: There are **8 stations** on line **PLT-S-B** in the current data; **1** is **HIGH** risk and **7** are **NORMAL**. Examples include:
- **PLT-S-B01** — **HIGH**
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
| PASS | 18.0 | How many stations are at high risk right now? |
| PASS | 17.7 | How many stations are currently down? |
| PASS | 23.4 | What are the 5 stations with the highest failure probability right now? |
| PASS | 18.1 | Which station type had the most failures? |
| PASS | 12.8 | What is the mean time to repair in minutes for each plant? |
| PASS | 19.1 | Which failure mode caused the most downtime? |
| PASS | 12.1 | What is the total parts cost per plant? |
| PASS | 19.0 | What share of repairs were preventive for each station type? |
| PASS | 12.3 | How many failures did Plant North have? |
| PASS | 18.0 | List the stations on line PLT-S-B with their current risk band. |

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
Genie text: **6 stations** currently need maintenance soon: **5 are HIGH risk** and **1 is ELEVATED**.

Examples include:
- **PLT-N-C01** (Plant North) — **99.86%** risk, **HIGH**, driven by **hydraulic_pressure_bar**
- **PLT-S-B01** (Plant South) — **99.28%** risk, **HIGH**, driven by **motor_current_a**
- **PLT-S-D01** (Plant South) — **97.08%** risk, **HIGH**, driven by **cycle_time_s**
- **PLT-S-A01** (Plant South) — **92.76%** risk, **HIGH**, driven by **cycle_time_s**
- **PLT-S-C04** (Plant South) — **70.83%** risk, **HIGH**, driven by **vibration_rms**

Plant South accounts for **4 of the 6** at-risk stations, and the risk levels range from **50.76%** to **99.86%**.
Genie SQL:
SELECT `station_id`, `plant_id`, `line_id`, `station_type`, `criticality`, `risk_band`, `failure_probability` * 100 AS `risk_pct`, `top_signal`, `top_signal_deviation_pct`, `last_reading_ts`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` IN ('HIGH', 'ELEVATED')
  AND `failure_probability` IS NOT NULL
ORDER BY `failure_probability` DESC, `station_id` ASC
rows: [['PLT-N-C01', 'PLT-N', 'PLT-N-C', 'press', 'high', 'HIGH', 99.92, 'hydraulic_pressure_bar', 10.1, datetime.datetime(2026, 10, 6, 17, 49, 9)], ['PLT-S-B01', 'PLT-S', 'PLT-S-B', 'press', 'medium', 'HIGH', 99.61, 'motor_current_a', 10.7, datetime.datetime(2026, 10, 6, 17, 49, 9)], ['PLT-S-A01', 'PLT-S', 'PLT-S-A', 'press', 'medium', 'HIGH', 97.96000000000001, 'cycle_time_s', 8.2, datetime.datetime(2026, 10, 6, 17, 49, 9)], ['PLT-S-D01', 'PLT-S', 'PLT-S-D', 'press', 'low', 'HIGH', 96.95, 'cycle_time_s', 11.0, datetime.datetime(2026, 10, 6, 17, 49, 9)], ['PLT-S-C04', 'PLT-S', 'PLT-S-C', 'robot_arm', 'low', 'ELEVATED', 48.38, 'vibration_rms', 19.7, datetime.datetime(2026, 10, 6, 17, 49, 9)]]

### Why is the riskiest station at risk?
Genie text: The riskiest station is **PLT-N-C01** in **PLT-N**, and **PLT-N-C01** is at risk because the top warning signal is **hydraulic_pressure_bar** with a **12.2%** deviation. **PLT-N-C01** has a maintenance risk of **99.9%** and is in the **HIGH** risk band, which makes **PLT-N-C01** the highest-risk station in the current view.
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
  WHERE failure_probability IS NOT NULL AND top_signal IS NOT NULL AND top_signal_deviation_pct IS NOT NULL
)
SELECT
  station_id,
  plant_id,
  line_id,
  station_type,
  ROUND(failure_probability * 100, 1) AS risk_pct,
  risk_band,
  top_signal,
  top_signal_deviation_pct
FROM ranked
WHERE risk_rank = 1
ORDER BY station_id ASC
rows: [['PLT-S-B01', 'PLT-S', 'PLT-S-B', 'press', 99.9, 'HIGH', 'motor_current_a', 12.4]]

### Which station types fail most often and what is their MTTR?
Genie text: The station type that fails most often is **cnc_mill** with **296** failures and an average repair time of **115.2 minutes**. Examples include:
- **cnc_mill** — **296** failures, **115.2 minutes** MTTR
- **press** — **280** failures, **110.8 minutes** MTTR
- **welder** — **260** failures, **112.5 minutes** MTTR
- **robot_arm** — **137** failures, **108.9 minutes** MTTR
- **conveyor** — **124** failures, **112.0 minutes** MTTR

Across these 5 station types, failure counts drop sharply after the top three, while MTTR stays fairly consistent at about **109 to 115 minutes**.
Genie SQL:
SELECT `Station Type`, MEASURE(`Failures`) AS `failures`, MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `failures` DESC
rows: [['cnc_mill', 296, 115.1976376037942], ['press', 280, 110.83746264557489], ['welder', 260, 112.50394617635841], ['robot_arm', 137, 108.85064914589415], ['conveyor', 124, 112.01279122873008]]

### How many open work orders do we have by priority?
Genie text: The visible result shows **Priority P1 = 0 open work orders**. In the returned data, **P1** is the only priority shown, so there are **no open work orders** in this result set.
Genie SQL:
SELECT
  `Priority`,
  MEASURE(`Open Work Orders`) AS `open_work_orders`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_order_metrics`
WHERE `Priority` IS NOT NULL
GROUP BY ALL
ORDER BY `open_work_orders` DESC
rows: [['P1', 0]]
```
