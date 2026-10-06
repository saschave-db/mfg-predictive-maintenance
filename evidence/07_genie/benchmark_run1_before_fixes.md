# Genie benchmark results

Space `01f1c10d662111078cd7326dff1774c6` · run 2026-10-06T17:08:38.560552+00:00 · **7/10 benchmark questions matched the reference SQL result** (values compared after rounding; Genie may add columns).

| verdict | seconds | question |
|---|---|---|
| FAIL | 19.2 | How many stations are at high risk right now? |
| PASS | 13.6 | How many stations are currently down? |
| FAIL | 19.0 | What are the 5 stations with the highest failure probability right now? |
| PASS | 18.7 | Which station type had the most failures? |
| PASS | 19.9 | What is the mean time to repair in minutes for each plant? |
| PASS | 17.9 | Which failure mode caused the most downtime? |
| PASS | 13.5 | What is the total parts cost per plant? |
| PASS | 19.1 | What share of repairs were preventive for each station type? |
| FAIL | 12.6 | How many failures did Plant North have? |
| PASS | 19.6 | List the stations on line PLT-S-B with their current risk band. |
| SAMPLE | 19.7 | Which stations need maintenance soon? |
| SAMPLE | 19.9 | Why is the riskiest station at risk? |
| SAMPLE | 18.8 | Which station types fail most often and what is their MTTR? |
| SAMPLE | 25.6 | How many open work orders do we have by priority? |

### FAIL: How many stations are at high risk right now?

Genie answered in 19.2 s (conversation `01f1c1a7ef98161ba267dfcf3a583696`).

Genie text: There are **3** stations at **HIGH** risk right now based on the current station health data. This means **3** stations have a failure probability of **70% or higher** within the current risk horizon.

Genie SQL:
```sql
SELECT COUNT(*) AS `high_risk_stations`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'HIGH'
```

Genie result:

| high_risk_stations |
|---|
| 3 |

Reference SQL:
```sql
SELECT count(*) AS high_risk_stations FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current WHERE risk_band = 'HIGH'
```

Reference result:

| high_risk_stations |
|---|
| 2 |


### PASS: How many stations are currently down?

Genie answered in 13.6 s (conversation `01f1c1a7fbf21b4d82a0864e842bbf24`).

Genie text: There are **0** stations currently down. Based on the current station status data, **no** stations are in the **DOWN** risk band right now.

Genie SQL:
```sql
SELECT COUNT(*) AS `stations_currently_down`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'DOWN'
```

Genie result:

| stations_currently_down |
|---|
| 0 |

Reference SQL:
```sql
SELECT count(*) AS stations_down FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current WHERE risk_band = 'DOWN'
```

Reference result:

| stations_down |
|---|
| 0 |


### FAIL: What are the 5 stations with the highest failure probability right now?

Genie answered in 19.0 s (conversation `01f1c1a804d41695bde6091da6df1a72`).

Genie text: Here are the **5 stations with the highest failure probability right now**:
- **PLT-N-C07** — **99.93%** (**HIGH**)
- **PLT-S-A06** — **99.15%** (**HIGH**)
- **PLT-S-C02** — **47.45%** (**ELEVATED**)
- **PLT-S-C08** — **37.86%** (**NORMAL**)
- **PLT-E-D07** — **31.01%** (**NORMAL**)

The top two stations are far above the rest and both fall in the **HIGH** risk band, while the remaining three are all below **50%**.

Genie SQL:
```sql
WITH `ranked` AS (
  SELECT
    `station_id`,
    `plant_id`,
    `line_id`,
    `station_type`,
    `failure_probability` * 100 AS `failure_probability_pct`,
    `risk_band`,
    `top_signal`,
    `top_signal_deviation_pct`,
    RANK() OVER (ORDER BY `failure_probability` DESC, `station_id` ASC) AS `rank`
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
FROM `ranked`
WHERE `rank` <= 5
ORDER BY `failure_probability_pct` DESC, `station_id` ASC
```

Genie result:

| station_id | plant_id | line_id | station_type | failure_probability_pct | risk_band | top_signal | top_signal_deviation_pct |
|---|---|---|---|---|---|---|---|
| PLT-N-C07 | PLT-N | PLT-N-C | welder | 99.92999999999999 | HIGH | bearing_temp_c | 26.2 |
| PLT-S-A06 | PLT-S | PLT-S-A | cnc_mill | 99.15 | HIGH | motor_current_a | 8.9 |
| PLT-S-C02 | PLT-S | PLT-S-C | cnc_mill | 47.449999999999996 | ELEVATED | vibration_rms | 9.4 |
| PLT-S-C08 | PLT-S | PLT-S-C | press | 37.86 | NORMAL | motor_current_a | 8.5 |
| PLT-E-D07 | PLT-E | PLT-E-D | welder | 31.009999999999998 | NORMAL | motor_current_a | 7.3 |

Reference SQL:
```sql
SELECT station_id, failure_probability FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 5
```

Reference result:

| station_id | failure_probability |
|---|---|
| PLT-N-C07 | 0.9993 |
| PLT-S-A06 | 0.9915 |
| PLT-S-C02 | 0.4745 |
| PLT-S-C08 | 0.3786 |
| PLT-E-D07 | 0.3101 |


### PASS: Which station type had the most failures?

Genie answered in 18.7 s (conversation `01f1c1a810e91100a9e4bee7fb441ec1`).

Genie text: The station type with the most failures is **cnc_mill**, with **296 failures**. Based on the result shown, **cnc_mill** is the top failure-driving station type in the maintenance data.

Genie SQL:
```sql
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
ORDER BY `failures` DESC, `Station Type` ASC;
```

Genie result:

| Station Type | failures |
|---|---|
| cnc_mill | 296 |

Reference SQL:
```sql
SELECT `Station Type`, MEASURE(`Failures`) AS failures FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY failures DESC LIMIT 1
```

Reference result:

| Station Type | failures |
|---|---|
| cnc_mill | 296 |


### PASS: What is the mean time to repair in minutes for each plant?

Genie answered in 19.9 s (conversation `01f1c1a81cf41b109c7f945fcb2771ba`).

Genie text: The mean time to repair is **112.77 minutes** for **Plant East**, **111.91 minutes** for **Plant North**, and **112.17 minutes** for **Plant South**. Across the 3 plants shown, repair times are very similar, with **Plant East** the highest and **Plant North** the lowest.

Genie SQL:
```sql
SELECT
  `Plant`,
  MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `Plant` ASC
```

Genie result:

| Plant | mttr_minutes |
|---|---|
| Plant East | 112.76728331661222 |
| Plant North | 111.91021343462346 |
| Plant South | 112.16677532169717 |

Reference SQL:
```sql
SELECT Plant, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY Plant
```

Reference result:

| Plant | mttr_min |
|---|---|
| Plant East | 112.76728331661222 |
| Plant North | 111.91021343462346 |
| Plant South | 112.16677532169717 |


### PASS: Which failure mode caused the most downtime?

Genie answered in 17.9 s (conversation `01f1c1a829dc1674932e616f6d8ac951`).

Genie text: The failure mode that caused the most downtime is **overheating**, with **56,431** downtime minutes. Based on the result shown, **overheating** is the top downtime driver among failure modes with recorded downtime.

Genie SQL:
```sql
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
```

Genie result:

| Failure Mode | downtime_minutes |
|---|---|
| overheating | 56431.49725154227 |

Reference SQL:
```sql
SELECT `Failure Mode`, MEASURE(`Downtime Minutes`) AS downtime_min FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics WHERE `Failure Mode` IS NOT NULL GROUP BY ALL ORDER BY downtime_min DESC LIMIT 1
```

Reference result:

| Failure Mode | downtime_min |
|---|---|
| overheating | 56431.49725154227 |


### PASS: What is the total parts cost per plant?

Genie answered in 13.5 s (conversation `01f1c1a8356b101eb02e5284db436444`).

Genie text: The total parts cost is highest for **Plant South** at **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across the 3 plants shown, **Plant South** has the highest total parts cost and **Plant North** the lowest.

Genie SQL:
```sql
SELECT `Plant`, MEASURE(`Parts Cost USD`) AS `parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `parts_cost_usd` DESC
```

Genie result:

| Plant | parts_cost_usd |
|---|---|
| Plant South | 2891611.356288852 |
| Plant East | 2713614.1188870384 |
| Plant North | 2518897.5788193042 |

Reference SQL:
```sql
SELECT Plant, MEASURE(`Parts Cost USD`) AS parts_cost_usd FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY Plant
```

Reference result:

| Plant | parts_cost_usd |
|---|---|
| Plant East | 2713614.1188870384 |
| Plant North | 2518897.5788193042 |
| Plant South | 2891611.356288852 |


### PASS: What share of repairs were preventive for each station type?

Genie answered in 19.1 s (conversation `01f1c1a83e691f07beb4298b91d9c984`).

Genie text: Preventive repairs ranged from **17.47%** to **21.21%** by station type. 
- **cnc_mill:** **18.28%**
- **conveyor:** **18.42%**
- **press:** **21.13%**
- **robot_arm:** **17.47%**
- **welder:** **21.21%**
Among the five station types shown, **welder** had the highest preventive share and **robot_arm** had the lowest.

Genie SQL:
```sql
SELECT
  `Station Type`,
  MEASURE(`Preventive Share`) AS `preventive_share`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `Station Type` ASC
```

Genie result:

| Station Type | preventive_share |
|---|---|
| cnc_mill | 0.1828254847645429 |
| conveyor | 0.1842105263157895 |
| press | 0.2112676056338028 |
| robot_arm | 0.1746987951807229 |
| welder | 0.2121212121212121 |

Reference SQL:
```sql
SELECT `Station Type`, MEASURE(`Preventive Share`) AS preventive_share FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY `Station Type`
```

Reference result:

| Station Type | preventive_share |
|---|---|
| cnc_mill | 0.1828254847645429 |
| conveyor | 0.1842105263157895 |
| press | 0.2112676056338028 |
| robot_arm | 0.1746987951807229 |
| welder | 0.2121212121212121 |


### FAIL: How many failures did Plant North have?

Genie answered in 12.6 s (conversation `01f1c1a84ab41817a48798b487d8ede0`).

Genie text: Plant North (**PLT-N**) had **0 failures**. In the returned result, the failure count for **PLT-N** is **0**, so there were no recorded failures in this data.

Genie SQL:
```sql
SELECT MEASURE(`Failures`) AS `failures`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` = 'PLT-N'
GROUP BY ALL
```

Genie result:

| failures |
|---|
| 0 |

Reference SQL:
```sql
SELECT MEASURE(`Failures`) AS failures FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics WHERE Plant = 'Plant North'
```

Reference result:

| failures |
|---|
| 340 |


### PASS: List the stations on line PLT-S-B with their current risk band.

Genie answered in 19.6 s (conversation `01f1c1a8531811cda900e2f014d02ec3`).

Genie text: All **8 stations** on line **PLT-S-B** are currently in the **NORMAL** risk band. Examples include:
- **PLT-S-B01** — **NORMAL**
- **PLT-S-B02** — **NORMAL**
- **PLT-S-B03** — **NORMAL**
- **PLT-S-B04** — **NORMAL**
- **PLT-S-B05** — **NORMAL**
This line shows a fully consistent current risk profile, with no stations above **NORMAL** in the visible data.

Genie SQL:
```sql
SELECT `station_id`, `risk_band`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `line_id` = 'PLT-S-B'
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `station_id` ASC
```

Genie result:

| station_id | risk_band |
|---|---|
| PLT-S-B01 | NORMAL |
| PLT-S-B02 | NORMAL |
| PLT-S-B03 | NORMAL |
| PLT-S-B04 | NORMAL |
| PLT-S-B05 | NORMAL |
| PLT-S-B06 | NORMAL |
| PLT-S-B07 | NORMAL |
| PLT-S-B08 | NORMAL |

Reference SQL:
```sql
SELECT station_id, risk_band FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current WHERE line_id = 'PLT-S-B' ORDER BY station_id
```

Reference result:

| station_id | risk_band |
|---|---|
| PLT-S-B01 | NORMAL |
| PLT-S-B02 | NORMAL |
| PLT-S-B03 | NORMAL |
| PLT-S-B04 | NORMAL |
| PLT-S-B05 | NORMAL |
| PLT-S-B06 | NORMAL |
| PLT-S-B07 | NORMAL |
| PLT-S-B08 | NORMAL |


### SAMPLE: Which stations need maintenance soon?

Genie answered in 19.7 s (conversation `01f1c1a85fbd1858b5edc09a16aaf131`).

Genie text: **4 stations** currently need maintenance soon, and all are in the **HIGH** risk band. They are **PLT-S-D04** (**99.77%**), **PLT-S-A06** (**99.43%**), **PLT-S-C02** (**77.61%**), and **PLT-E-D07** (**71.35%**); based on these results, **Plant South** has **3 of the 4** at-risk stations shown.

Genie SQL:
```sql
SELECT `station_id`, `plant_id`, `line_id`, `station_type`, `risk_band`, `failure_probability` * 100 AS `risk_pct`, `top_signal`, `top_signal_deviation_pct`, `last_reading_ts`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` IN ('HIGH', 'ELEVATED')
  AND `failure_probability` IS NOT NULL
ORDER BY `failure_probability` DESC, `station_id` ASC
```

Genie result:

| station_id | plant_id | line_id | station_type | risk_band | risk_pct | top_signal | top_signal_deviation_pct | last_reading_ts |
|---|---|---|---|---|---|---|---|---|
| PLT-S-D04 | PLT-S | PLT-S-D | robot_arm | HIGH | 99.77000000000001 | bearing_temp_c | 15.9 | 2026-10-06T17:06:19.000Z |
| PLT-S-A06 | PLT-S | PLT-S-A | cnc_mill | HIGH | 99.42999999999999 | spindle_rpm | 39.5 | 2026-10-06T17:06:19.000Z |
| PLT-S-C02 | PLT-S | PLT-S-C | cnc_mill | HIGH | 77.61 | vibration_rms | 11.2 | 2026-10-06T17:06:19.000Z |
| PLT-E-D07 | PLT-E | PLT-E-D | welder | HIGH | 71.35000000000001 | spindle_rpm | 6.8 | 2026-10-06T17:06:19.000Z |


### SAMPLE: Why is the riskiest station at risk?

Genie answered in 19.9 s (conversation `01f1c1a86bb91d148d42c09884159a6d`).

Genie text: The riskiest station is **station PLT-S-D04** in **plant PLT-S**, **line PLT-S-D**; **station type robot_arm** is in **HIGH** risk with a **99.6%** maintenance risk within the horizon. The main reason **station PLT-S-D04** is at risk is **bearing_temp_c**, which is running **19.8%** above its expected level; in this result, **station PLT-S-D04** is the single highest-risk station returned.

Genie SQL:
```sql
WITH ranked AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    risk_band,
    failure_probability,
    top_signal,
    top_signal_deviation_pct,
    RANK() OVER (ORDER BY failure_probability DESC) AS rnk
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE failure_probability IS NOT NULL AND top_signal IS NOT NULL AND top_signal_deviation_pct IS NOT NULL
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
WHERE rnk = 1
ORDER BY failure_probability DESC, station_id ASC
```

Genie result:

| station_id | plant_id | line_id | station_type | risk_band | risk_pct | top_signal | top_signal_deviation_pct |
|---|---|---|---|---|---|---|---|
| PLT-S-D04 | PLT-S | PLT-S-D | robot_arm | HIGH | 99.6 | bearing_temp_c | 19.8 |


### SAMPLE: Which station types fail most often and what is their MTTR?

Genie answered in 18.8 s (conversation `01f1c1a877e617b6b82420e2cd9758eb`).

Genie text: Would you prefer to see the median MTTR instead of the average, or count unique failure events rather than total failures?

Genie SQL:
```sql
SELECT
  `Station Type`,
  MEASURE(`Failures`) AS `failures`,
  MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `failures` DESC
```

Genie result:

| Station Type | failures | mttr_minutes |
|---|---|---|
| cnc_mill | 296 | 115.1976376037942 |
| press | 280 | 110.83746264557489 |
| welder | 260 | 112.50394617635841 |
| robot_arm | 137 | 108.85064914589415 |
| conveyor | 124 | 112.01279122873008 |


### SAMPLE: How many open work orders do we have by priority?

Genie answered in 25.6 s (conversation `01f1c1a8836010c8ae61660ce679c13c`).

Genie text: There are **0 open work orders** in the current data, so there are **no priorities with any open items**. This means the open work order backlog is currently **empty**.

Genie SQL:
```sql
SELECT `priority` AS `Priority`, COUNT(*) AS `open_work_orders` FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_orders_current` WHERE `completed_at` IS NULL GROUP BY `priority` ORDER BY `open_work_orders` DESC
```

Genie result:

| Priority | open_work_orders |
|---|---|

