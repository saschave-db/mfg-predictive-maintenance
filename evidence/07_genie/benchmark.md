# Genie benchmark results

Space `01f1c10d662111078cd7326dff1774c6` · run 2026-10-09T16:44:16.928292+00:00 · **12/12 benchmark questions matched the reference SQL result** (Genie's SQL and the reference SQL are executed back to back on the same warehouse; values compared after rounding; Genie may add columns).

| verdict | seconds | question |
|---|---|---|
| PASS | 13.4 | How many stations are at high risk right now? |
| PASS | 13.0 | How many stations are currently down? |
| PASS | 18.7 | What are the 5 stations with the highest failure probability right now? |
| PASS | 19.9 | Which station type had the most failures? |
| PASS | 13.3 | What is the mean time to repair in minutes for each plant? |
| PASS | 18.1 | Which failure mode caused the most downtime? |
| PASS | 13.4 | What is the total parts cost per plant? |
| PASS | 13.3 | What share of repairs were preventive for each station type? |
| PASS | 13.0 | How many failures did Plant North have? |
| PASS | 12.4 | List the stations on line PLT-S-B with their current risk band. |
| PASS | 20.0 | Which line has the highest risk-weighted OEM delivery exposure right now, and which OEM program does it supply? |
| PASS | 18.8 | What is the JIS buffer in minutes for each line supplying Nordvik Motors? |
| SAMPLE | 18.0 | Which stations need maintenance soon? |
| SAMPLE | 18.3 | Why is the riskiest station at risk? |
| SAMPLE | 13.0 | Which station types fail most often and what is their MTTR? |
| SAMPLE | 19.4 | How many open work orders do we have by priority? |
| SAMPLE | 20.0 | Which OEM programs are exposed to a line stop right now? |

### PASS: How many stations are at high risk right now?

Genie answered in 13.4 s (conversation `01f1c3fff2aa186a849f27a086d9cfaf`).

Genie text: There are **2** stations at **HIGH** risk right now. Based on the current station snapshot, the count of stations with risk band **HIGH** is **2**.

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

Genie answered in 13.0 s (conversation `01f1c3fffb9a1d8ba9c3ae3067c77a52`).

Genie text: There are **0** stations currently marked as **DOWN** in `pdm_core.station_health_current`, so **no stations are currently down**.

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

Genie answered in 18.7 s (conversation `01f1c40004691eef9d9d30e579721aa4`).

Genie text: The **5 stations with the highest failure probability right now** are:
- **PLT-N-C01** at **99.9%** (**HIGH** risk), top signal: **hydraulic_pressure_bar**
- **PLT-S-B01** at **99.73%** (**HIGH** risk), top signal: **motor_current_a**
- **PLT-E-D07** at **51.45%** (**ELEVATED** risk), top signal: **cycle_time_s**
- **PLT-E-A02** at **48.39%** (**ELEVATED** risk), top signal: **motor_current_a**
- **PLT-S-C02** at **25.28%** (**NORMAL** risk), top signal: **vibration_rms**

The top two stations are clear outliers, both near **100%** failure probability, while the remaining three are materially lower.

Genie SQL:
```sql
WITH `ranked_stations` AS (
  SELECT
    `station_id`,
    `plant_id`,
    `line_id`,
    `station_type`,
    `risk_band`,
    `failure_probability`,
    `top_signal`,
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
  `failure_probability`,
  `top_signal`
FROM `ranked_stations`
WHERE `rank` <= 5
ORDER BY `failure_probability` DESC, `station_id` ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | risk_band | failure_probability | top_signal |
|---|---|---|---|---|---|---|
| PLT-N-C01 | PLT-N | PLT-N-C | press | HIGH | 0.999 | hydraulic_pressure_bar |
| PLT-S-B01 | PLT-S | PLT-S-B | press | HIGH | 0.9973 | motor_current_a |
| PLT-E-D07 | PLT-E | PLT-E-D | welder | ELEVATED | 0.5145 | cycle_time_s |
| PLT-E-A02 | PLT-E | PLT-E-A | cnc_mill | ELEVATED | 0.4839 | motor_current_a |
| PLT-S-C02 | PLT-S | PLT-S-C | cnc_mill | NORMAL | 0.2528 | vibration_rms |

Reference SQL:
```sql
SELECT station_id FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 5
```

Reference result:

| station_id |
|---|
| PLT-N-C01 |
| PLT-S-B01 |
| PLT-E-D07 |
| PLT-E-A02 |
| PLT-S-C02 |


### PASS: Which station type had the most failures?

Genie answered in 19.9 s (conversation `01f1c40010c11401b36cbdc4ea466946`).

Genie text: The station type with the most failures is **cnc_mill**, with **296** failures. In the result shown, **cnc_mill** ranks highest for failures.

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
ORDER BY `failure_rank` ASC, `Station Type` ASC;
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

Genie answered in 13.3 s (conversation `01f1c4001ea11f12b137e67f9d4d8afe`).

Genie text: The mean time to repair is **112.77 minutes** for **Plant East**, **111.91 minutes** for **Plant North**, and **112.17 minutes** for **Plant South**. Across all 3 plants, repair times are very similar, with less than **1 minute** separating the highest and lowest values.

Genie SQL:
```sql
SELECT `Plant`, MEASURE(`Mean Time To Repair Minutes`) AS `mttr_minutes`
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

Genie answered in 18.1 s (conversation `01f1c40028271951824f434ebcc6301e`).

Genie text: The failure mode with the most downtime is **overheating**, with **56,431** downtime minutes. Based on the result shown, **overheating** is the top downtime driver.

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
ORDER BY `downtime_rank` ASC, `Failure Mode` ASC;
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

Genie answered in 13.4 s (conversation `01f1c400346812219c3e385c8f111a54`).

Genie text: The total parts cost is highest for **Plant South** at **$2,891,611.36**, followed by **Plant East** at **$2,713,614.12** and **Plant North** at **$2,518,897.58**. Across the 3 plants shown, **Plant South** leads and **Plant North** is lowest.

Genie SQL:
```sql
SELECT `Plant`, MEASURE(`Parts Cost USD`) AS `parts_cost_usd`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Plant` IS NOT NULL
GROUP BY ALL
ORDER BY `parts_cost_usd` DESC
```

Genie SQL result (re-executed next to the reference):

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

Genie answered in 13.3 s (conversation `01f1c4003dc6196c9b9d04d4cd735a80`).

Genie text: Preventive repairs accounted for **21.21%** of work on **welder** stations, **21.13%** on **press** stations, **18.42%** on **conveyor** stations, **18.28%** on **cnc_mill** stations, and **17.47%** on **robot_arm** stations. Across the 5 station types shown, **welder** had the highest preventive share and **robot_arm** the lowest.

Genie SQL:
```sql
SELECT
  `Station Type`,
  MEASURE(`Preventive Share`) AS `preventive_share`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`maintenance_metrics`
WHERE `Station Type` IS NOT NULL
GROUP BY ALL
ORDER BY `preventive_share` DESC
```

Genie SQL result (re-executed next to the reference):

| Station Type | preventive_share |
|---|---|
| welder | 0.2121212121212121 |
| press | 0.2112676056338028 |
| conveyor | 0.1842105263157895 |
| cnc_mill | 0.1828254847645429 |
| robot_arm | 0.1746987951807229 |

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

Genie answered in 13.0 s (conversation `01f1c40047581677a3c9fbbfdc677bdc`).

Genie text: Plant North had **340 failures**.

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

Genie answered in 12.4 s (conversation `01f1c40050411600a311d02efe22ef55`).

Genie text: There are **8 stations** on line **PLT-S-B**; **PLT-S-B01** is **HIGH** risk, and the other **7 stations** are **NORMAL**. Examples include:
- **PLT-S-B01** — **HIGH**
- **PLT-S-B02** — **NORMAL**
- **PLT-S-B03** — **NORMAL**
- **PLT-S-B04** — **NORMAL**
- **PLT-S-B05** — **NORMAL**

Genie SQL:
```sql
SELECT `station_id`, `risk_band`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `line_id` = 'PLT-S-B'
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `station_id` ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | risk_band |
|---|---|
| PLT-S-B01 | HIGH |
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
| PLT-S-B01 | HIGH |
| PLT-S-B02 | NORMAL |
| PLT-S-B03 | NORMAL |
| PLT-S-B04 | NORMAL |
| PLT-S-B05 | NORMAL |
| PLT-S-B06 | NORMAL |
| PLT-S-B07 | NORMAL |
| PLT-S-B08 | NORMAL |


### PASS: Which line has the highest risk-weighted OEM delivery exposure right now, and which OEM program does it supply?

Genie answered in 20.0 s (conversation `01f1c40058e61a26ae321bd5cec86b68`).

Genie text: The line with the **highest** risk-weighted OEM delivery exposure right now is **PLT-S-B** at plant **PLT-S**, with **$912,604.0** in risk-weighted exposure. Line **PLT-S-B** supplies OEM customer **Fjord Electric** for vehicle program **FE Pace Sedan**.

Genie SQL:
```sql
WITH `ranked` AS (
  SELECT
    `line_id`,
    `plant_id`,
    `oem_customer`,
    `vehicle_program`,
    `risk_weighted_exposure_usd`,
    RANK() OVER (ORDER BY `risk_weighted_exposure_usd` DESC) AS `rnk`
  FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`oem_delivery_exposure`
  WHERE `risk_weighted_exposure_usd` IS NOT NULL
    AND `line_id` IS NOT NULL
)
SELECT
  `line_id`,
  `plant_id`,
  `oem_customer`,
  `vehicle_program`,
  `risk_weighted_exposure_usd`
FROM `ranked`
WHERE `rnk` = 1
```

Genie SQL result (re-executed next to the reference):

| line_id | plant_id | oem_customer | vehicle_program | risk_weighted_exposure_usd |
|---|---|---|---|---|
| PLT-S-B | PLT-S | Fjord Electric | FE Pace Sedan | 912604.0 |

Reference SQL:
```sql
SELECT line_id, vehicle_program FROM serverless_stable_am1uc2_catalog.pdm_ops.oem_delivery_exposure ORDER BY risk_weighted_exposure_usd DESC LIMIT 1
```

Reference result:

| line_id | vehicle_program |
|---|---|
| PLT-S-B | FE Pace Sedan |


### PASS: What is the JIS buffer in minutes for each line supplying Nordvik Motors?

Genie answered in 18.8 s (conversation `01f1c400670a1864bb2d79174a454021`).

Genie text: Nordvik Motors has **4** supplying lines in the data, with JIS buffers ranging from **60 to 90 minutes**.

- **PLT-E-D**: **90 minutes**
- **PLT-N-A**: **60 minutes**
- **PLT-N-B**: **75 minutes**
- **PLT-N-C**: **60 minutes**

The longest buffer is on **PLT-E-D**, while **PLT-N-A** and **PLT-N-C** share the shortest buffer.

Genie SQL:
```sql
SELECT `plant_id`, `line_id`, `jis_buffer_min`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`oem_delivery_exposure`
WHERE `oem_customer` = 'Nordvik Motors'
  AND `plant_id` IS NOT NULL
  AND `line_id` IS NOT NULL
  AND `jis_buffer_min` IS NOT NULL
ORDER BY `plant_id` ASC, `line_id` ASC
```

Genie SQL result (re-executed next to the reference):

| plant_id | line_id | jis_buffer_min |
|---|---|---|
| PLT-E | PLT-E-D | 90 |
| PLT-N | PLT-N-A | 60 |
| PLT-N | PLT-N-B | 75 |
| PLT-N | PLT-N-C | 60 |

Reference SQL:
```sql
SELECT line_id, jis_buffer_min FROM serverless_stable_am1uc2_catalog.pdm_ops.oem_delivery_exposure WHERE oem_customer = 'Nordvik Motors' ORDER BY line_id
```

Reference result:

| line_id | jis_buffer_min |
|---|---|
| PLT-E-D | 90 |
| PLT-N-A | 60 |
| PLT-N-B | 75 |
| PLT-N-C | 60 |


### SAMPLE: Which stations need maintenance soon?

Genie answered in 18.0 s (conversation `01f1c40074ab14d6954762d874de9fd6`).

Genie text: Would you prefer to see stations needing maintenance soon including only those at high risk, or also those at elevated risk?

Genie SQL:
```sql
SELECT `station_id`, `plant_id`, `line_id`, `station_type`, `risk_band`, `failure_probability` * 100 AS `risk_pct`, `top_signal`, `top_signal_deviation_pct`, `last_reading_ts`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `risk_band` IN ('HIGH', 'ELEVATED')
  AND `failure_probability` IS NOT NULL
  AND `station_id` IS NOT NULL
  AND `risk_band` IS NOT NULL
ORDER BY `failure_probability` DESC, `station_id` ASC
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | risk_band | risk_pct | top_signal | top_signal_deviation_pct | last_reading_ts |
|---|---|---|---|---|---|---|---|---|
| PLT-N-C01 | PLT-N | PLT-N-C | press | HIGH | 99.9 | hydraulic_pressure_bar | 11.0 | 2026-10-07T23:44:09.000Z |
| PLT-S-B01 | PLT-S | PLT-S-B | press | HIGH | 99.72999999999999 | motor_current_a | 13.6 | 2026-10-07T23:44:09.000Z |
| PLT-E-D07 | PLT-E | PLT-E-D | welder | ELEVATED | 51.449999999999996 | cycle_time_s | 13.0 | 2026-10-07T23:44:09.000Z |
| PLT-E-A02 | PLT-E | PLT-E-A | cnc_mill | ELEVATED | 48.39 | motor_current_a | 9.4 | 2026-10-07T23:44:09.000Z |


### SAMPLE: Why is the riskiest station at risk?

Genie answered in 18.3 s (conversation `01f1c4007fa715ff8500275986bfcb82`).

Genie text: The riskiest station is **PLT-N-C01** in plant **PLT-N** on line **PLT-N-C**, and it is at risk because the top signal is **hydraulic_pressure_bar** with a **11.0%** deviation. Station **PLT-N-C01** is a **press** with **99.9%** failure probability and a **HIGH** risk band, which indicates a very urgent maintenance risk.

Genie SQL:
```sql
WITH ranked AS (
  SELECT
    station_id,
    plant_id,
    line_id,
    station_type,
    ROUND(failure_probability * 100, 1) AS risk_pct,
    risk_band,
    top_signal,
    top_signal_deviation_pct,
    RANK() OVER (ORDER BY failure_probability DESC) AS risk_rank
  FROM serverless_stable_am1uc2_catalog.pdm_core.station_health_current
  WHERE failure_probability IS NOT NULL AND station_id IS NOT NULL
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
```

Genie SQL result (re-executed next to the reference):

| station_id | plant_id | line_id | station_type | risk_pct | risk_band | top_signal | top_signal_deviation_pct |
|---|---|---|---|---|---|---|---|
| PLT-N-C01 | PLT-N | PLT-N-C | press | 99.9 | HIGH | hydraulic_pressure_bar | 11.0 |


### SAMPLE: Which station types fail most often and what is their MTTR?

Genie answered in 13.0 s (conversation `01f1c4008ad51416a5b1e7050b6b490f`).

Genie text: The station type with the most failures is **cnc_mill** with **296** failures and an average repair time of **115.2 minutes**. Examples include:
- **cnc_mill** — **296** failures, **115.2 minutes** MTTR
- **press** — **280** failures, **110.8 minutes** MTTR
- **welder** — **260** failures, **112.5 minutes** MTTR
- **robot_arm** — **137** failures, **108.9 minutes** MTTR
- **conveyor** — **124** failures, **112.0 minutes** MTTR
Across these 5 station types, repair times are fairly similar, ranging from about **108.9** to **115.2 minutes** even as failure counts vary widely.

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

Genie answered in 19.4 s (conversation `01f1c40092d61b8da9c7e874865edd0d`).

Genie text: The visible results show **0** open work orders for **P1** priority and **0** for **P2** priority. Across the **2** priorities returned, there are **no open work orders** in the data shown.

Genie SQL:
```sql
SELECT
  `Priority`,
  MEASURE(`Open Work Orders`) AS `open_work_orders`
FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`work_order_metrics`
WHERE `Priority` IS NOT NULL
GROUP BY ALL
ORDER BY `open_work_orders` DESC
```

Genie SQL result (re-executed next to the reference):

| Priority | open_work_orders |
|---|---|
| P1 | 0 |
| P2 | 0 |


### SAMPLE: Which OEM programs are exposed to a line stop right now?

Genie answered in 20.0 s (conversation `01f1c4009ea318dc89452eae46c6e42c`).

Genie text: There are **12** OEM program/line combinations currently exposed to a line stop; the highest current exposure is concentrated in **FE Pace Sedan** for Fjord Electric on **PLT-S-B**, followed by **NV-e5 Crossover** for Nordvik Motors on **PLT-N-C**. Examples include:
- **FE Pace Sedan** — Fjord Electric, **PLT-S-B**: **$912,604** risk-weighted exposure, **51 min** line stop, riskiest station **PLT-S-B01** (**HIGH**)
- **NV-e5 Crossover** — Nordvik Motors, **PLT-N-C**: **$609,440** risk-weighted exposure, **51 min** line stop, riskiest station **PLT-N-C01** (**HIGH**)
- **Aurora A3 Hatch** — Aurora Elbil, **PLT-E-A**: **$293,812** risk-weighted exposure, **55 min** line stop, riskiest station **PLT-E-A02** (**ELEVATED**)
- **Aurora X5 SUV** — Aurora Elbil, **PLT-E-C**: **$128,110** risk-weighted exposure, **64 min** line stop, riskiest station **PLT-E-C04** (**NORMAL**)
- **NV-e5 Crossover** — Nordvik Motors, **PLT-E-D**: **$104,205** risk-weighted exposure, **23 min** line stop, riskiest station **PLT-E-D07** (**ELEVATED**)

Across the 12 exposed combinations, risk-weighted exposure ranges from **$8,852** to **$912,604**, with only the top two currently tied to **HIGH** risk bands.

Genie SQL:
```sql
SELECT `plant_id`, `line_id`, `oem_customer`, `vehicle_program`, `oem_line_stop_min_if_fails`, `exposure_usd_if_fails`, `risk_weighted_exposure_usd`, `riskiest_station_id`, `riskiest_risk_band` FROM `serverless_stable_am1uc2_catalog`.`pdm_ops`.`oem_delivery_exposure` WHERE `oem_line_stop_min_if_fails` IS NOT NULL AND `oem_line_stop_min_if_fails` > 0 AND `vehicle_program` IS NOT NULL AND `risk_weighted_exposure_usd` IS NOT NULL ORDER BY `risk_weighted_exposure_usd` DESC, `exposure_usd_if_fails` DESC, `vehicle_program` ASC
```

Genie SQL result (re-executed next to the reference):

| plant_id | line_id | oem_customer | vehicle_program | oem_line_stop_min_if_fails | exposure_usd_if_fails | risk_weighted_exposure_usd | riskiest_station_id | riskiest_risk_band |
|---|---|---|---|---|---|---|---|---|
| PLT-S | PLT-S-B | Fjord Electric | FE Pace Sedan | 51.0 | 915074.0 | 912604.0 | PLT-S-B01 | HIGH |
| PLT-N | PLT-N-C | Nordvik Motors | NV-e5 Crossover | 51.0 | 610050.0 | 609440.0 | PLT-N-C01 | HIGH |
| PLT-E | PLT-E-A | Aurora Elbil | Aurora A3 Hatch | 55.0 | 607174.0 | 293812.0 | PLT-E-A02 | ELEVATED |
| PLT-E | PLT-E-C | Aurora Elbil | Aurora X5 SUV | 64.0 | 1021610.0 | 128110.0 | PLT-E-C04 | NORMAL |
| PLT-E | PLT-E-D | Nordvik Motors | NV-e5 Crossover | 23.0 | 202536.0 | 104205.0 | PLT-E-D07 | ELEVATED |
| PLT-S | PLT-S-C | Fjord Electric | FE Haul Van | 40.0 | 401976.0 | 101620.0 | PLT-S-C02 | NORMAL |
| PLT-S | PLT-S-A | Fjord Electric | FE Pace Sedan | 70.0 | 1263557.0 | 68232.0 | PLT-S-A06 | NORMAL |
| PLT-N | PLT-N-B | Nordvik Motors | NV-e7 SUV | 36.0 | 537562.0 | 44403.0 | PLT-N-B01 | NORMAL |
| PLT-N | PLT-N-A | Nordvik Motors | NV-e7 SUV | 55.0 | 827965.0 | 42392.0 | PLT-N-A06 | NORMAL |
| PLT-E | PLT-E-B | Aurora Elbil | Aurora A3 Hatch | 36.0 | 394212.0 | 17542.0 | PLT-E-B01 | NORMAL |

... 2 more rows

