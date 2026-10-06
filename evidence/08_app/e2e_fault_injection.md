# End-to-end fault injection through the app

Run 2026-10-06T17:20:47.304585+00:00 against `https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com`.
Station **PLT-E-A03**, injected at **2026-10-06T17:12:38.582498+00:00**, first HIGH seen in the app at **17:16:25** (UTC).
Every line below is a real API call to the deployed Databricks App.

`17:12:38` **GET /api/stations** (660 ms)
Fleet before injection: {'NORMAL': 93, 'ELEVATED': 1, 'HIGH': 2}; data age 49.3 s; Lakebase query 31.6 ms. Target **PLT-E-A03** at 0.9% (NORMAL).
`17:12:38` **POST /api/inject** (121 ms) body `{"station_id": "PLT-E-A03", "failure_mode": "overheating"}`
Command #1 queued at 2026-10-06T17:12:38.582498+00:00.

| time (UTC) | risk | band | top signal | deviation % | temp °C | current A | window end | data age s |
|---|---|---|---|---|---|---|---|---|
| 17:12:38 | 0.9% | NORMAL | motor_current_a | 8.6 | 62.2 | 130.3 | 17:11:50 | 49.7 |
| 17:12:49 | 0.9% | NORMAL | motor_current_a | 8.6 | 62.2 | 130.3 | 17:11:50 | 59.9 |
| 17:12:59 | 1.1% | NORMAL | motor_current_a | 8.5 | 62.2 | 130.2 | 17:12:10 | 50.2 |
| 17:13:09 | 1.1% | NORMAL | motor_current_a | 8.5 | 62.2 | 130.2 | 17:12:10 | 60.5 |
| 17:13:20 | 1.1% | NORMAL | motor_current_a | 8.4 | 62.1 | 130.1 | 17:12:30 | 50.8 |
| 17:13:30 | 1.1% | NORMAL | motor_current_a | 8.4 | 62.1 | 130.1 | 17:12:30 | 61.2 |
| 17:13:40 | 0.9% | NORMAL | cycle_time_s | 8.3 | 62.1 | 130.0 | 17:12:50 | 51.5 |
| 17:13:50 | 0.9% | NORMAL | cycle_time_s | 8.3 | 62.1 | 130.0 | 17:12:50 | 61.8 |
| 17:14:01 | 1.1% | NORMAL | cycle_time_s | 8.3 | 62.2 | 129.9 | 17:13:10 | 52.1 |
| 17:14:11 | 1.1% | NORMAL | cycle_time_s | 8.3 | 62.2 | 129.9 | 17:13:10 | 62.4 |
| 17:14:21 | 0.7% | NORMAL | motor_current_a | 7.9 | 62.1 | 129.5 | 17:13:30 | 52.7 |
| 17:14:32 | 0.6% | NORMAL | motor_current_a | 7.8 | 62.2 | 129.4 | 17:13:40 | 53.0 |
| 17:14:42 | 0.6% | NORMAL | motor_current_a | 7.8 | 62.2 | 129.3 | 17:13:50 | 53.3 |
| 17:14:52 | 0.8% | NORMAL | motor_current_a | 7.7 | 62.2 | 129.3 | 17:14:00 | 53.6 |
| 17:15:03 | 0.9% | NORMAL | motor_current_a | 7.7 | 62.3 | 129.2 | 17:14:10 | 53.9 |
| 17:15:13 | 1.9% | NORMAL | motor_current_a | 7.6 | 62.5 | 129.1 | 17:14:20 | 54.1 |
| 17:15:23 | 1.8% | NORMAL | motor_current_a | 7.5 | 62.6 | 128.9 | 17:14:30 | 54.5 |
| 17:15:33 | 2.5% | NORMAL | motor_current_a | 7.6 | 62.7 | 129.2 | 17:14:40 | 54.8 |
| 17:15:44 | 2.9% | NORMAL | motor_current_a | 7.7 | 62.9 | 129.2 | 17:14:50 | 55.1 |
| 17:15:54 | 32.9% | NORMAL | motor_current_a | 7.9 | 63.3 | 129.4 | 17:15:10 | 45.4 |
| 17:16:04 | 32.9% | NORMAL | motor_current_a | 7.9 | 63.3 | 129.4 | 17:15:10 | 55.7 |
| 17:16:15 | 67.7% | ELEVATED | motor_current_a | 8.5 | 63.9 | 130.2 | 17:15:30 | 46.3 |
| 17:16:25 | 78.7% | HIGH | motor_current_a | 8.8 | 64.1 | 130.6 | 17:15:40 | 46.6 |

`17:16:25` **POST /api/work_orders** (107 ms) body `{"station_id": "PLT-E-A03", "priority": "P1", "description": "E2E test: overheating alert"}`
Work order #1 created: priority P1, risk at creation 78.7%, top signal motor_current_a.
`17:17:28` **POST /api/whatif** (62261 ms) body `{"station_id": "PLT-E-A03", "sensor": "bearing_temp_c", "change_pct": -10}`
What-if (bearing temp -10%) via `pdm-station-risk`: now 78.7% -> scenario 64.4% (serving round trip 62158.8 ms).
`17:17:43` **POST /api/genie** (15088 ms) body `{"question": "Why is station PLT-E-A03 at risk right now?"}`
Genie answer: Station **PLT-E-A03** is at risk right now because the top warning signal is **motor_current_a**, which is running **10.4%** away from its expected level. Station **PLT-E-A03** is currently in **HIGH** risk status with a **98.36%** maintenance risk score, based on the latest reading at **2026-10-06 17:16:29 UTC** and scoring time **2026-10-06 17:17:04 UTC**.

Genie SQL:
```sql
SELECT `station_id`, `plant_id`, `line_id`, `station_type`, `risk_band`, `failure_probability` * 100 AS `risk_pct`, `top_signal`, `top_signal_deviation_pct`, `last_reading_ts`, `scored_at`
FROM `serverless_stable_am1uc2_catalog`.`pdm_core`.`station_health_current`
WHERE `station_id` = 'PLT-E-A03'
```
Genie rows: `[['PLT-E-A03', 'PLT-E', 'PLT-E-A', 'welder', 'HIGH', '98.36', 'motor_current_a', '10.4', '2026-10-06T17:16:29.000Z', '2026-10-06T17:17:04.064Z']]`
`17:17:43` **POST /api/work_orders/1/complete** (101 ms)
Work order #1 completed at 2026-10-06T17:17:43.289537+00:00; repair command queued.

| time (UTC) | risk | band | window end |
|---|---|---|---|
| 17:17:43 | 99.0% | HIGH | 17:16:50 |
| 17:17:58 | 99.5% | HIGH | 17:17:00 |
| 17:18:14 | 99.7% | HIGH | 17:17:20 |
| 17:18:29 | 99.8% | HIGH | 17:17:40 |
| 17:18:44 | 99.0% | HIGH | 17:17:50 |
| 17:19:00 | 95.8% | HIGH | 17:18:10 |
| 17:19:15 | 97.5% | HIGH | 17:18:30 |
| 17:19:30 | 97.5% | HIGH | 17:18:30 |
| 17:19:46 | 93.7% | HIGH | 17:18:50 |
| 17:20:01 | 96.1% | HIGH | 17:19:10 |
| 17:20:16 | 96.3% | HIGH | 17:19:30 |
| 17:20:31 | 97.8% | HIGH | 17:19:40 |
| 17:20:47 | 1.2% | NORMAL | 17:19:50 |
