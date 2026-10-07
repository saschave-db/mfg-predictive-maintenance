# Executed notebook: E08_end_to_end

Exported from Databricks job run `994447175034582` (task `E08_end_to_end`, task run `472079048977763`).

Result: **SUCCESS** · start 2026-10-07T23:05:46.571000+00:00 · end 2026-10-07T23:14:01.994000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


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
target station: PLT-S-B06 | current risk: 0.0014
command 7 requested at 2026-10-07 23:05:59.258649+00:00
| command_id | status | requested_at | applied_at |
|---|---|---|---|
| 7 | applied | 2026-10-07 23:05:59.258649+00:00 | 2026-10-07 23:06:01.001355+00:00 |
```

Output:

```text
{"text/plain": "[[7,\n  'applied',\n  datetime.datetime(2026, 10, 7, 23, 5, 59, 258649, tzinfo=datetime.timezone.utc),\n  datetime.datetime(2026, 10, 7, 23, 6, 1, 1355, tzinfo=datetime.timezone.utc)]]"}
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
| 23:06:05 | 23:05:20 | 0.2% | NORMAL | 23:05:20 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 23:06:23 | 23:05:30 | 0.5% | NORMAL | 23:05:20 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 23:06:39 | 23:05:40 | 0.4% | NORMAL | 23:05:40 | 0.4% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:06:55 | 23:06:10 | 0.5% | NORMAL | 23:06:10 | 0.5% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:07:11 | 23:06:20 | 0.4% | NORMAL | 23:06:20 | 0.4% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:07:29 | 23:06:40 | 0.4% | NORMAL | 23:06:40 | 0.4% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:07:45 | 23:07:00 | 0.3% | NORMAL | 23:07:00 | 0.3% | NORMAL | hydraulic_pressure_bar | 1.56 |
| 23:08:01 | 23:07:10 | 0.2% | NORMAL | 23:07:10 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:08:18 | 23:07:30 | 0.2% | NORMAL | 23:07:30 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 23:08:34 | 23:07:50 | 0.2% | NORMAL | 23:07:50 | 0.2% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:08:51 | 23:08:00 | 0.1% | NORMAL | 23:08:00 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.54 |
| 23:09:08 | 23:08:20 | 0.1% | NORMAL | 23:08:20 | 0.1% | NORMAL | hydraulic_pressure_bar | 1.55 |
| 23:09:24 | 23:08:40 | 0.2% | NORMAL | 23:08:30 | 0.1% | NORMAL | motor_current_a | 1.55 |
| 23:09:40 | 23:08:50 | 0.2% | NORMAL | 23:08:50 | 0.2% | NORMAL | motor_current_a | 1.56 |
| 23:09:56 | 23:09:10 | 0.6% | NORMAL | 23:09:00 | 0.5% | NORMAL | motor_current_a | 1.56 |
| 23:10:13 | 23:09:20 | 2.0% | NORMAL | 23:09:20 | 2.0% | NORMAL | motor_current_a | 1.64 |
| 23:10:28 | 23:09:40 | 3.0% | NORMAL | 23:09:40 | 3.0% | NORMAL | vibration_rms | 1.68 |
| 23:10:45 | 23:10:00 | 18.1% | NORMAL | 23:10:00 | 18.1% | NORMAL | vibration_rms | 1.73 |
| 23:11:01 | 23:10:10 | 18.8% | NORMAL | 23:10:10 | 18.8% | NORMAL | vibration_rms | 1.76 |
| 23:11:17 | 23:10:30 | 30.8% | NORMAL | 23:10:30 | 30.8% | NORMAL | vibration_rms | 1.84 |
| 23:11:33 | 23:10:50 | 33.7% | NORMAL | 23:10:50 | 33.7% | NORMAL | vibration_rms | 1.92 |
| 23:11:50 | 23:11:10 | 37.5% | NORMAL | 23:11:10 | 37.5% | NORMAL | vibration_rms | 2.03 |
| 23:12:06 | 23:11:20 | 75.9% | HIGH | 23:11:20 | 75.9% | HIGH | vibration_rms | 2.03 |
first delta_elevated: 23:12:06 UTC, 367 s after injection
first delta_high: 23:12:06 UTC, 367 s after injection
first postgres_elevated: 23:12:06 UTC, 367 s after injection
first postgres_high: 23:12:06 UTC, 367 s after injection

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
work order 4 created at 2026-10-07 23:12:06.472146+00:00 with risk 0.7595 HIGH top signal vibration_rms
work order completed; repair command 8 at 2026-10-07 23:12:26.498801+00:00
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
| 23:12:26 | 23:11:30 | 79.0% | HIGH |
| 23:12:41 | 23:11:50 | 92.0% | HIGH |
| 23:12:56 | 23:12:10 | 89.1% | HIGH |
| 23:13:11 | 23:12:20 | 90.3% | HIGH |
| 23:13:26 | 23:12:40 | 55.3% | ELEVATED |
| 23:13:41 | 23:12:50 | 33.5% | NORMAL |
| 23:13:56 | 23:13:00 | 2.5% | NORMAL |
recovered: 2026-10-07 23:13:56.687514+00:00 (90 s after repair)

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
| 7 | inject_fault | applied | 2026-10-07 23:05:59.258649+00:00 | 2026-10-07 23:06:01.001355+00:00 | 1.74 |
| 8 | repair | applied | 2026-10-07 23:12:26.498801+00:00 | 2026-10-07 23:12:27.001374+00:00 | 0.50 |

Output:

| window_end | risk_pct | risk_band | top_signal | vibration | acoustic_db | temp_c |
|---|---|---|---|---|---|---|
| 2026-10-07T23:05:00.000Z | 0.1 | NORMAL | hydraulic_pressure_bar | 1.53 | 73.7 | 47.9 |
| 2026-10-07T23:05:30.000Z | 0.5 | NORMAL | hydraulic_pressure_bar | 1.54 | 73.7 | 48.0 |
| 2026-10-07T23:06:00.000Z | 0.3 | NORMAL | hydraulic_pressure_bar | 1.55 | 73.7 | 48.1 |
| 2026-10-07T23:06:30.000Z | 0.4 | NORMAL | hydraulic_pressure_bar | 1.55 | 73.7 | 48.1 |
| 2026-10-07T23:07:00.000Z | 0.3 | NORMAL | hydraulic_pressure_bar | 1.56 | 73.6 | 48.2 |
| 2026-10-07T23:07:30.000Z | 0.2 | NORMAL | hydraulic_pressure_bar | 1.54 | 73.6 | 48.3 |
| 2026-10-07T23:08:00.000Z | 0.1 | NORMAL | hydraulic_pressure_bar | 1.54 | 73.7 | 48.4 |
| 2026-10-07T23:08:30.000Z | 0.1 | NORMAL | motor_current_a | 1.55 | 73.7 | 48.7 |
| 2026-10-07T23:09:00.000Z | 0.5 | NORMAL | motor_current_a | 1.56 | 74.0 | 49.0 |
| 2026-10-07T23:09:30.000Z | 3.5 | NORMAL | vibration_rms | 1.66 | 74.3 | 49.4 |
| 2026-10-07T23:10:00.000Z | 18.1 | NORMAL | vibration_rms | 1.73 | 74.5 | 49.8 |
| 2026-10-07T23:10:30.000Z | 30.8 | NORMAL | vibration_rms | 1.84 | 75.0 | 50.3 |
| 2026-10-07T23:11:00.000Z | 38.0 | NORMAL | vibration_rms | 1.98 | 75.3 | 50.7 |
| 2026-10-07T23:11:30.000Z | 79.0 | HIGH | vibration_rms | 2.09 | 75.7 | 51.1 |
| 2026-10-07T23:12:00.000Z | 88.8 | HIGH | vibration_rms | 2.3 | 76.3 | 51.6 |
| 2026-10-07T23:12:30.000Z | 69.1 | ELEVATED | vibration_rms | 2.52 | 76.9 | 52.0 |
| 2026-10-07T23:13:00.000Z | 2.5 | NORMAL | vibration_rms | 2.35 | 76.3 | 51.3 |

Output:

```text
{'station': 'PLT-S-B06', 'injected_at': '2026-10-07 23:05:59.258649+00:00', 'delta_elevated': '2026-10-07 23:12:06.343379+00:00', 'delta_high': '2026-10-07 23:12:06.343382+00:00', 'postgres_elevated': '2026-10-07 23:12:06.343383+00:00', 'postgres_high': '2026-10-07 23:12:06.343385+00:00', 'work_order': 4, 'repair_at': '2026-10-07 23:12:26.498801+00:00', 'recovered_at': '2026-10-07 23:13:56.687514+00:00', 'station_went_down': False}
```
