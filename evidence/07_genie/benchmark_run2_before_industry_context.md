# Genie benchmark results

Space `01f1c10d662111078cd7326dff1774c6` · run 2026-10-06T17:15:49.338987+00:00 · **10/10 benchmark questions matched the reference SQL result** (Genie's SQL and the reference SQL are executed back to back on the same warehouse; values compared after rounding; Genie may add columns).

| verdict | seconds | question |
|---|---|---|
| PASS | 13.2 | How many stations are at high risk right now? |
| PASS | 13.5 | How many stations are currently down? |
| PASS | 20.1 | What are the 5 stations with the highest failure probability right now? |
| PASS | 14.3 | Which station type had the most failures? |
| PASS | 12.8 | What is the mean time to repair in minutes for each plant? |
| PASS | 13.7 | Which failure mode caused the most downtime? |
| PASS | 14.2 | What is the total parts cost per plant? |
| PASS | 13.6 | What share of repairs were preventive for each station type? |
| PASS | 12.9 | How many failures did Plant North have? |
| PASS | 13.9 | List the stations on line PLT-S-B with their current risk band. |
| SAMPLE | 20.1 | Which stations need maintenance soon? |
| SAMPLE | 19.0 | Why is the riskiest station at risk? |
| SAMPLE | 18.2 | Which station types fail most often and what is their MTTR? |
| SAMPLE | 25.1 | How many open work orders do we have by priority? |

### PASS: How many stations are at high risk right now?

Genie answered in 13.2 s (conversation `01f1c1a8ffad1ac291ad1d2a084402fe`).

Genie text: There are **2** stations at **high risk** right now. Based on the current station snapshot, the count of stations with risk band **HIGH** is **2**.

Genie SQL:
```sql
SELECT COUNT(*) AS `high_risk_stations`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'HIGH'
```

Genie SQL result (re-executed next to the reference):

| high_risk_stations |
|---|
| 2 |

Reference SQL:
```sql
SELECT count(*) AS high_risk_stations FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current WHERE risk_band = 'HIGH'
```

Reference result:

| high_risk_stations |
|---|
| 2 |


### PASS: How many stations are currently down?

Genie answered in 13.5 s (conversation `01f1c1a908da15f99401f225a53d87cf`).

Genie text: There are **0 stations currently down** based on `pdm_core.station_health_current` where `risk_band = 'DOWN'`. The current result shows **no stations** in the down status right now.

Genie SQL:
```sql
SELECT COUNT(*) AS `stations_down`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` = 'DOWN'
```

Genie SQL result (re-executed next to the reference):

| stations_down |
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


### PASS: What are the 5 stations with the highest failure probability right now?

Genie answered in 20.1 s (conversation `01f1c1a912061d409ae4318dc1092c4e`).

Genie text: Here are the **5 stations with the highest failure probability right now**:
- **PLT-S-C08** — **99.9%** (**HIGH**), top signal: **hydraulic_pressure_bar**
- **PLT-S-A02** — **96.4%** (**HIGH**), top signal: **vibration_rms**
- **PLT-N-A08** — **45.6%** (**ELEVATED**), top signal: **vibration_rms**
- **PLT-E-D07** — **25.5%** (**NORMAL**), top signal: **cycle_time_s**
- **PLT-S-C03** — **22.3%** (**NORMAL**), top signal: **motor_current_a**

The top two stations are clear outliers and both are in **Plant South**, while the remaining three are well below 50% risk.

Genie SQL:
```sql
WITH ranked_stations AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    ROUND(failure_probability * 100, 1) AS failure_probability_pct,
    risk_band,
    top_signal,
    RANK() OVER (ORDER BY failure_probability DESC) AS risk_rank
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
FROM ranked_stations
WHERE risk_rank <= 5
ORDER BY failure_probability_pct DESC, station_id ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | failure_probability_pct | risk_band | top_signal |
|---|---|---|---|---|---|---|
| PLT-S-C08 | PLT-S | PLT-S-C | press | 99.9 | HIGH | spindle_rpm |
| PLT-S-A02 | PLT-S | PLT-S-A | cnc_mill | 97.8 | HIGH | vibration_rms |
| PLT-N-A08 | PLT-N | PLT-N-A | press | 36.1 | NORMAL | vibration_rms |
| PLT-E-C05 | PLT-E | PLT-E-C | conveyor | 22.4 | NORMAL | acoustic_db |
| PLT-E-D05 | PLT-E | PLT-E-D | conveyor | 19.3 | NORMAL | bearing_temp_c |

Reference SQL:
```sql
SELECT station_id FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 5
```

Reference result:

| station_id |
|---|
| PLT-S-C08 |
| PLT-S-A02 |
| PLT-N-A08 |
| PLT-E-C05 |
| PLT-E-D05 |


### PASS: Which station type had the most failures?

Genie answered in 14.3 s (conversation `01f1c1a91f951aabbbf79a4cbde368b7`).

Genie text: The station type with the most failures is **cnc_mill**, with **296** failures. Based on the result shown, **cnc_mill** is the top failure-driving station type in the maintenance data.

Genie SQL:
```sql
WITH ranked_failures AS (
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
FROM ranked_failures
WHERE `failure_rank` <= 1
ORDER BY `failures` DESC, `Station Type` ASC
```

Genie SQL result (re-executed next to the reference):

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

Genie answered in 12.8 s (conversation `01f1c1a9296d1a5081ab3b0da5c18a7f`).

Genie text: The mean time to repair is **112.77 minutes** for **Plant East**, **111.91 minutes** for **Plant North**, and **112.17 minutes** for **Plant South**. Across all 3 plants, repair times are very similar, with less than **1 minute** separating the highest and lowest values.

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

Genie SQL result (re-executed next to the reference):

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

Genie answered in 13.7 s (conversation `01f1c1a93244149aae8892ed813ef3a6`).

Genie text: The failure mode that caused the most downtime was **overheating**, with **56,431** downtime minutes. Based on the result shown, **overheating** ranked highest for downtime among failure modes with recorded downtime.

Genie SQL:
```sql
WITH `downtime_by_mode` AS (
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
FROM `downtime_by_mode`
WHERE `downtime_rank` <= 1
ORDER BY `downtime_minutes` DESC, `Failure Mode` ASC
```

Genie SQL result (re-executed next to the reference):

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

Genie answered in 14.2 s (conversation `01f1c1a93be31f728b4a7b293a8fed45`).

Genie text: The total parts cost is highest for **Plant South** at **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across the 3 plants shown, **Plant South** has the highest total parts cost and **Plant North** the lowest.

Genie SQL:
```sql
SELECT
  `Plant`,
  MEASURE(`Parts Cost USD`) AS `total_parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `total_parts_cost_usd` DESC
```

Genie SQL result (re-executed next to the reference):

| Plant | total_parts_cost_usd |
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

Genie answered in 13.6 s (conversation `01f1c1a9458411fc9e638e727b7d5082`).

Genie text: Preventive repairs accounted for **17.47% to 21.21%** of repairs across the 5 station types shown, with **welder** highest and **robot_arm** lowest.

- **cnc_mill:** **18.28%**
- **conveyor:** **18.42%**
- **press:** **21.13%**
- **robot_arm:** **17.47%**
- **welder:** **21.21%**

Overall, preventive work was about **one-fifth or less** of repairs for every station type in this result.

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

Genie SQL result (re-executed next to the reference):

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


### PASS: How many failures did Plant North have?

Genie answered in 12.9 s (conversation `01f1c1a94ed611639137189b98add213`).

Genie text: **Plant North** had **340 failures**. Based on the single result shown, the total failures for **Plant North** in this query is **340**.

Genie SQL:
```sql
SELECT MEASURE(`Failures`) AS `failures`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` = 'Plant North'
GROUP BY ALL
```

Genie SQL result (re-executed next to the reference):

| failures |
|---|
| 340 |

Reference SQL:
```sql
SELECT MEASURE(`Failures`) AS failures FROM serverless_stable_am1uc2_catalog.pdm_ops.maintenance_metrics WHERE Plant = 'Plant North'
```

Reference result:

| failures |
|---|
| 340 |


### PASS: List the stations on line PLT-S-B with their current risk band.

Genie answered in 13.9 s (conversation `01f1c1a957c41538b652188b92ba9fe8`).

Genie text: All **8 stations** on line **PLT-S-B** are currently in the **NORMAL** risk band.

- **PLT-S-B01** — **NORMAL**
- **PLT-S-B02** — **NORMAL**
- **PLT-S-B03** — **NORMAL**
- **PLT-S-B04** — **NORMAL**
- **PLT-S-B05** — **NORMAL**

Genie SQL:
```sql
SELECT
  `station_id`,
  `risk_band`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `line_id` = 'PLT-S-B'
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `station_id` ASC
```

Genie SQL result (re-executed next to the reference):

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

Genie answered in 20.1 s (conversation `01f1c1a96175151ea4046c66c4ca2bb7`).

Genie text: **3 stations** currently need maintenance soon based on elevated or high risk.
- **PLT-S-A02** (Plant South) — **HIGH** risk at **100.0%**, driven by **bearing_temp_c** (**26.3%** deviation)
- **PLT-N-A08** (Plant North) — **HIGH** risk at **70.8%**, driven by **vibration_rms** (**39.7%** deviation)
- **PLT-E-C05** (Plant East) — **ELEVATED** risk at **59.5%**, driven by **vibration_rms** (**23.3%** deviation)
The highest-risk station is **PLT-S-A02**, and **vibration_rms** is the leading issue for 2 of the 3 stations shown.

Genie SQL:
```sql
SELECT station_id, plant_id, line_id, station_type, risk_band, ROUND(failure_probability * 100, 1) AS risk_pct, top_signal, top_signal_deviation_pct, last_reading_ts
FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
WHERE risk_band IN ('HIGH', 'ELEVATED')
  AND failure_probability IS NOT NULL
  AND risk_band IS NOT NULL
ORDER BY failure_probability DESC, station_id ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | risk_band | risk_pct | top_signal | top_signal_deviation_pct | last_reading_ts |
|---|---|---|---|---|---|---|---|---|
| PLT-S-A02 | PLT-S | PLT-S-A | cnc_mill | HIGH | 100.0 | bearing_temp_c | 26.3 | 2026-10-06T17:13:39.000Z |
| PLT-N-A08 | PLT-N | PLT-N-A | press | HIGH | 70.8 | vibration_rms | 39.7 | 2026-10-06T17:13:39.000Z |
| PLT-E-C05 | PLT-E | PLT-E-C | conveyor | ELEVATED | 59.5 | vibration_rms | 23.3 | 2026-10-06T17:13:39.000Z |


### SAMPLE: Why is the riskiest station at risk?

Genie answered in 19.0 s (conversation `01f1c1a96db11fe484aa6ae97523d154`).

Genie text: The riskiest station is **PLT-S-A02** in plant **PLT-S** on line **PLT-S-A**, with a **100.0%** maintenance risk and risk band **HIGH**. Station **PLT-S-A02** is at risk because the top warning signal is **bearing_temp_c**, which is running **27.9%** above normal for the **cnc_mill** station.

Genie SQL:
```sql
WITH ranked AS (
  SELECT
    station_health_current.station_id,
    station_health_current.plant_id,
    station_health_current.line_id,
    station_health_current.station_type,
    station_health_current.risk_band,
    station_health_current.failure_probability,
    station_health_current.top_signal,
    station_health_current.top_signal_deviation_pct,
    RANK() OVER (ORDER BY station_health_current.failure_probability DESC) AS risk_rank
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE station_health_current.failure_probability IS NOT NULL
    AND station_health_current.top_signal IS NOT NULL
    AND station_health_current.top_signal_deviation_pct IS NOT NULL
)
SELECT
  ranked.station_id,
  ranked.plant_id,
  ranked.line_id,
  ranked.station_type,
  ranked.risk_band,
  ROUND(ranked.failure_probability * 100, 1) AS risk_pct,
  ranked.top_signal,
  ranked.top_signal_deviation_pct
FROM ranked
WHERE ranked.risk_rank = 1
ORDER BY ranked.failure_probability DESC, ranked.station_id ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | risk_band | risk_pct | top_signal | top_signal_deviation_pct |
|---|---|---|---|---|---|---|---|
| PLT-S-A02 | PLT-S | PLT-S-A | cnc_mill | HIGH | 100.0 | bearing_temp_c | 27.9 |


### SAMPLE: Which station types fail most often and what is their MTTR?

Genie answered in 18.2 s (conversation `01f1c1a9794a14aa880736ad90fc3dd4`).

Genie text: The station type with the most failures is **cnc_mill** with **296** failures and an average repair time of **115.2 minutes**. Examples include:
- **cnc_mill** — **296** failures, **115.2 minutes** MTTR
- **press** — **280** failures, **110.8 minutes** MTTR
- **welder** — **260** failures, **112.5 minutes** MTTR
- **robot_arm** — **137** failures, **108.9 minutes** MTTR
- **conveyor** — **124** failures, **112.0 minutes** MTTR
Across these 5 station types, MTTR is fairly consistent at about **109 to 115 minutes**, so the biggest difference is failure frequency rather than repair duration.

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

Genie SQL result (re-executed next to the reference):

| Station Type | failures | mttr_minutes |
|---|---|---|
| cnc_mill | 296 | 115.1976376037942 |
| press | 280 | 110.83746264557489 |
| welder | 260 | 112.50394617635841 |
| robot_arm | 137 | 108.85064914589415 |
| conveyor | 124 | 112.01279122873008 |


### SAMPLE: How many open work orders do we have by priority?

Genie answered in 25.1 s (conversation `01f1c1a9845f1ef692a74e3e91ac6d30`).

Genie text: There are **no open work orders with a recorded priority** in the current data, as the query returned **0 rows**. Based on these results, there is **nothing to break out by priority** right now.

Genie SQL:
```sql
SELECT `priority` AS `Priority`, COUNT(*) AS `open_work_orders` FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_orders_current` WHERE `completed_at` IS NULL AND `priority` IS NOT NULL GROUP BY `priority` ORDER BY `open_work_orders` DESC, `Priority` ASC
```

Genie SQL result (re-executed next to the reference):

| Priority | open_work_orders |
|---|---|

