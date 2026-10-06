# Executed notebook: E08_end_to_end

Exported from Databricks job run `980301348000608` (task `E08_end_to_end`, task run `175823207056605`).

Result: **SUCCESS** · start 2026-10-06T17:51:40.307000+00:00 · end 2026-10-06T17:59:07.512000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


# E08 · End-to-end live run: fault -> alert -> work order -> repair -> recovery

This notebook drives the full loop itself, the same way the app does:
1. Pick a healthy station and write an `inject_fault` command into Lakebase `pdm_ops.sim_commands`.
2. The running Zerobus simulator picks it up (every 2 s) and the station starts degrading.
3. Watch the risk score in **Delta** (`pdm_core.station_risk_scores`) and in **Postgres** (`pdm_live.station_risk_scores`)
   every 15 s until the station is HIGH in Postgres, where the app reads it.
4. Create a P1 work order in Lakebase, then complete it, which writes a `repair` command.
5. Watch the station return to NORMAL. A prevented failure: the station never goes DOWN.

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
import time, datetime
spark.sql(f"USE CATALOG {CATALOG}")
conn = pg()
ME = w.current_user.me().user_name
utc = lambda: datetime.datetime.now(datetime.timezone.utc)
```

## 1 · Pick a healthy CNC mill (bearing wear) and inject the fault

```python
cand = conn.run("""SELECT station_id, failure_probability FROM (SELECT DISTINCT ON (station_id) * FROM pdm_live.station_risk_scores
                   WHERE window_end > now() - interval '5 minutes' ORDER BY station_id, window_end DESC) l
                   WHERE station_type = 'cnc_mill' AND risk_band = 'NORMAL' AND failure_probability < 0.05
                   ORDER BY failure_probability LIMIT 1""")
STATION = cand[0][0]
print("target station:", STATION, "| current risk:", cand[0][1])
cmd = conn.run("""INSERT INTO pdm_ops.sim_commands (command, station_id, failure_mode, requested_by)
                  VALUES ('inject_fault', :s, 'bearing_wear', :u) RETURNING command_id, requested_at""", s=STATION, u=ME)
CMD_ID, INJECTED_AT = cmd[0]
print("command", CMD_ID, "requested at", INJECTED_AT)
time.sleep(5)
pg_table(conn, "SELECT command_id, status, requested_at, applied_at FROM pdm_ops.sim_commands WHERE command_id = :c", {"c": CMD_ID})
```

Output:

```text
target station: PLT-S-B06 | current risk: 0.001
command 3 requested at 2026-10-06 17:51:52.893947+00:00
| command_id | status | requested_at | applied_at |
|---|---|---|---|
| 3 | applied | 2026-10-06 17:51:52.893947+00:00 | 2026-10-06 17:51:53.002039+00:00 |
```

Output:

```text
{"text/plain": "[[3,\n  'applied',\n  datetime.datetime(2026, 10, 6, 17, 51, 52, 893947, tzinfo=datetime.timezone.utc),\n  datetime.datetime(2026, 10, 6, 17, 51, 53, 2039, tzinfo=datetime.timezone.utc)]]"}
```

## 2 · Watch Delta and Postgres until the station is HIGH where the app reads it

```python
print("| t (UTC) | Delta window | Delta risk | Delta band | Postgres window | Postgres risk | Postgres band | top signal | vibration |")
print("|---|---|---|---|---|---|---|---|---|")
first = {}
t_start = time.time()
while time.time() - t_start < 900:
    d = spark.sql(f"""SELECT window_end, failure_probability, risk_band FROM pdm_core.station_risk_scores
                      WHERE station_id = '{STATION}' ORDER BY window_end DESC LIMIT 1""").first()
    p = conn.run("""SELECT window_end, failure_probability, risk_band, top_signal, avg_vibration_rms FROM pdm_live.station_risk_scores
                    WHERE station_id = :s ORDER BY window_end DESC LIMIT 1""", s=STATION)[0]
    print(f"| {utc():%H:%M:%S} | {d.window_end:%H:%M:%S} | {d.failure_probability:.1%} | {d.risk_band} | "
          f"{p[0]:%H:%M:%S} | {float(p[1]):.1%} | {p[2]} | {p[3]} | {float(p[4]):.2f} |")
    for where, band in (("delta", d.risk_band), ("postgres", p[2])):
        if band in ("ELEVATED", "HIGH") and f"{where}_elevated" not in first:
            first[f"{where}_elevated"] = utc()
        if band == "HIGH" and f"{where}_high" not in first:
            first[f"{where}_high"] = utc()
    if "postgres_high" in first:
        break
    time.sleep(15)
for k, v in first.items():
    print(f"first {k}: {v:%H:%M:%S} UTC, {(v - INJECTED_AT).total_seconds():.0f} s after injection")
```

Output:

| t (UTC) | Delta window | Delta risk | Delta band | Postgres window | Postgres risk | Postgres band | top signal | vibration |
|---|---|---|---|---|---|---|---|---|
| 17:51:59 | 17:51:10 | 0.1% | NORMAL | 17:51:10 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.56 |
| 17:52:17 | 17:51:30 | 0.1% | NORMAL | 17:51:20 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.56 |
| 17:52:33 | 17:51:40 | 0.1% | NORMAL | 17:51:40 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.53 |
| 17:52:50 | 17:52:00 | 0.1% | NORMAL | 17:51:50 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 17:53:06 | 17:52:20 | 0.1% | NORMAL | 17:52:10 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 17:53:22 | 17:52:30 | 0.2% | NORMAL | 17:52:30 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 17:53:39 | 17:52:50 | 0.3% | NORMAL | 17:52:40 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 17:53:55 | 17:53:10 | 0.6% | NORMAL | 17:53:00 | 0.5% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 17:54:11 | 17:53:20 | 0.7% | NORMAL | 17:53:10 | 0.6% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 17:54:27 | 17:53:40 | 0.8% | NORMAL | 17:53:30 | 0.7% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 17:54:43 | 17:53:50 | 0.9% | NORMAL | 17:53:50 | 0.9% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 17:55:00 | 17:54:10 | 0.4% | NORMAL | 17:54:10 | 0.4% | NORMAL | hydraulic_pressure_bar | 1.57 |
| 17:55:16 | 17:54:30 | 1.1% | NORMAL | 17:54:20 | 0.5% | NORMAL | hydraulic_pressure_bar | 1.58 |
| 17:55:32 | 17:54:50 | 5.6% | NORMAL | 17:54:50 | 5.6% | NORMAL | vibration_rms | 1.68 |
| 17:55:48 | 17:55:00 | 21.9% | NORMAL | 17:55:00 | 21.9% | NORMAL | vibration_rms | 1.75 |
| 17:56:05 | 17:55:10 | 32.2% | NORMAL | 17:55:10 | 32.2% | NORMAL | vibration_rms | 1.78 |
| 17:56:21 | 17:55:40 | 35.0% | NORMAL | 17:55:40 | 35.0% | NORMAL | vibration_rms | 1.90 |
| 17:56:37 | 17:55:50 | 42.7% | ELEVATED | 17:55:40 | 35.0% | NORMAL | vibration_rms | 1.90 |
| 17:56:54 | 17:56:00 | 43.4% | ELEVATED | 17:56:00 | 43.4% | ELEVATED | vibration_rms | 2.01 |
| 17:57:10 | 17:56:20 | 37.4% | NORMAL | 17:56:20 | 37.4% | NORMAL | vibration_rms | 2.16 |
| 17:57:26 | 17:56:40 | 88.8% | HIGH | 17:56:40 | 88.8% | HIGH | vibration_rms | 2.34 |
first delta_elevated: 17:56:37 UTC, 285 s after injection
first postgres_elevated: 17:56:54 UTC, 302 s after injection
first delta_high: 17:57:26 UTC, 334 s after injection
first postgres_high: 17:57:26 UTC, 334 s after injection

## 3 · Act: work order, then complete it (writes a repair command)

```python
st = conn.run("""SELECT plant_id, line_id, failure_probability, risk_band, top_signal FROM pdm_live.station_risk_scores
                 WHERE station_id = :s ORDER BY window_end DESC LIMIT 1""", s=STATION)[0]
wo = conn.run("""INSERT INTO pdm_ops.work_orders (station_id, plant_id, line_id, priority, failure_probability, risk_band, top_signal,
                                                 description, created_by)
                 VALUES (:s, :p, :l, 'P1', :fp, :rb, :ts, 'E08 notebook: predicted bearing wear', :u) RETURNING work_order_id, created_at""",
              s=STATION, p=st[0], l=st[1], fp=st[2], rb=st[3], ts=st[4], u=ME)
WO_ID = wo[0][0]
print("work order", WO_ID, "created at", wo[0][1], "with risk", st[2], st[3], "top signal", st[4])
time.sleep(20)
conn.run("UPDATE pdm_ops.work_orders SET status = 'completed', completed_at = now(), updated_at = now() WHERE work_order_id = :w", w=WO_ID)
rep = conn.run("""INSERT INTO pdm_ops.sim_commands (command, station_id, requested_by) VALUES ('repair', :s, :u)
                  RETURNING command_id, requested_at""", s=STATION, u=ME)
REPAIR_AT = rep[0][1]
print("work order completed; repair command", rep[0][0], "at", REPAIR_AT)
```

Output:

```text
work order 2 created at 2026-10-06 17:57:26.883429+00:00 with risk 0.8876 HIGH top signal vibration_rms
work order completed; repair command 4 at 2026-10-06 17:57:46.905634+00:00
```

## 4 · Recovery

```python
print("| t (UTC) | Postgres window | risk | band |\n|---|---|---|---|")
t0, recovered = time.time(), None
while time.time() - t0 < 420:
    p = conn.run("""SELECT window_end, failure_probability, risk_band FROM pdm_live.station_risk_scores
                    WHERE station_id = :s ORDER BY window_end DESC LIMIT 1""", s=STATION)[0]
    print(f"| {utc():%H:%M:%S} | {p[0]:%H:%M:%S} | {float(p[1]):.1%} | {p[2]} |")
    if p[2] == "NORMAL" and float(p[1]) < 0.2:
        recovered = utc()
        break
    time.sleep(15)
print("recovered:", recovered, f"({(recovered - REPAIR_AT).total_seconds():.0f} s after repair)" if recovered else "")
```

Output:

| t (UTC) | Postgres window | risk | band |
|---|---|---|---|
| 17:57:46 | 17:57:00 | 93.0% | HIGH |
| 17:58:01 | 17:57:10 | 93.6% | HIGH |
| 17:58:17 | 17:57:30 | 92.7% | HIGH |
| 17:58:32 | 17:57:40 | 93.2% | HIGH |
| 17:58:47 | 17:57:50 | 85.4% | HIGH |
| 17:59:02 | 17:58:10 | 6.7% | NORMAL |
recovered: 2026-10-06 17:59:02.024269+00:00 (75 s after repair)

## 5 · Summary from the system of record

```python
pg_table(conn, """SELECT command_id, command, status, requested_at, applied_at,
                         round(extract(epoch FROM applied_at - requested_at)::numeric, 2) AS seconds_to_apply
                  FROM pdm_ops.sim_commands WHERE station_id = :s ORDER BY command_id""", {"s": STATION})
display(spark.sql(f"""
SELECT window_end, round(failure_probability * 100, 1) AS risk_pct, risk_band, top_signal, round(avg_vibration_rms, 2) AS vibration,
       round(avg_acoustic_db, 1) AS acoustic_db, round(avg_bearing_temp_c, 1) AS temp_c
FROM pdm_core.station_risk_scores WHERE station_id = '{STATION}'
  AND window_end >= timestamp'{INJECTED_AT:%Y-%m-%d %H:%M:%S}' - INTERVAL 1 MINUTE AND second(window_end) % 30 = 0
ORDER BY window_end"""))
print({"station": STATION, "injected_at": str(INJECTED_AT), **{k: str(v) for k, v in first.items()},
       "work_order": WO_ID, "repair_at": str(REPAIR_AT), "recovered_at": str(recovered),
       "station_went_down": spark.sql(f"""SELECT count(*) FROM pdm_core.station_risk_scores WHERE station_id = '{STATION}'
                                          AND risk_band = 'DOWN' AND window_end >= timestamp'{INJECTED_AT:%Y-%m-%d %H:%M:%S}'""").first()[0] > 0})
```

Output:

| command_id | command | status | requested_at | applied_at | seconds_to_apply |
|---|---|---|---|---|---|
| 3 | inject_fault | applied | 2026-10-06 17:51:52.893947+00:00 | 2026-10-06 17:51:53.002039+00:00 | 0.11 |
| 4 | repair | applied | 2026-10-06 17:57:46.905634+00:00 | 2026-10-06 17:57:47.001418+00:00 | 0.10 |

Output:

| window_end | risk_pct | risk_band | top_signal | vibration | acoustic_db | temp_c |
|---|---|---|---|---|---|---|
| 2026-10-06T17:51:00.000Z | 0.1 | NORMAL | hydraulic_pressure_bar | 1.56 | 73.7 | 47.7 |
| 2026-10-06T17:51:30.000Z | 0.1 | NORMAL | hydraulic_pressure_bar | 1.52 | 73.7 | 47.7 |
| 2026-10-06T17:52:00.000Z | 0.1 | NORMAL | hydraulic_pressure_bar | 1.54 | 73.7 | 47.7 |
| 2026-10-06T17:52:30.000Z | 0.2 | NORMAL | hydraulic_pressure_bar | 1.55 | 73.6 | 47.7 |
| 2026-10-06T17:53:00.000Z | 0.5 | NORMAL | hydraulic_pressure_bar | 1.55 | 73.6 | 47.7 |
| 2026-10-06T17:53:30.000Z | 0.7 | NORMAL | hydraulic_pressure_bar | 1.54 | 73.7 | 47.8 |
| 2026-10-06T17:54:00.000Z | 0.5 | NORMAL | hydraulic_pressure_bar | 1.56 | 73.8 | 48.0 |
| 2026-10-06T17:54:30.000Z | 1.1 | NORMAL | hydraulic_pressure_bar | 1.59 | 74.1 | 48.4 |
| 2026-10-06T17:55:00.000Z | 21.9 | NORMAL | vibration_rms | 1.75 | 74.7 | 48.8 |
| 2026-10-06T17:55:30.000Z | 33.5 | NORMAL | vibration_rms | 1.86 | 74.9 | 49.2 |
| 2026-10-06T17:56:00.000Z | 43.4 | ELEVATED | vibration_rms | 2.01 | 75.5 | 49.8 |
| 2026-10-06T17:56:30.000Z | 84.9 | HIGH | vibration_rms | 2.25 | 76.1 | 50.4 |
| 2026-10-06T17:57:00.000Z | 93.0 | HIGH | vibration_rms | 2.46 | 76.7 | 51.1 |
| 2026-10-06T17:57:30.000Z | 92.7 | HIGH | vibration_rms | 2.87 | 77.8 | 51.8 |
| 2026-10-06T17:58:00.000Z | 21.2 | NORMAL | vibration_rms | 3.08 | 78.0 | 51.8 |

Output:

```text
{'station': 'PLT-S-B06', 'injected_at': '2026-10-06 17:51:52.893947+00:00', 'delta_elevated': '2026-10-06 17:56:37.894904+00:00', 'postgres_elevated': '2026-10-06 17:56:54.545896+00:00', 'delta_high': '2026-10-06 17:57:26.783864+00:00', 'postgres_high': '2026-10-06 17:57:26.783866+00:00', 'work_order': 2, 'repair_at': '2026-10-06 17:57:46.905634+00:00', 'recovered_at': '2026-10-06 17:59:02.024269+00:00', 'station_went_down': False}
```
