# Databricks notebook source
# MAGIC %md
# MAGIC # E08 · End-to-end live run: fault -> alert -> work order -> repair -> recovery
# MAGIC
# MAGIC This notebook drives the full loop itself, the same way the app does:
# MAGIC 1. Pick a healthy station and write an `inject_fault` command into Lakebase `pdm_ops.sim_commands`.
# MAGIC 2. The running Zerobus simulator picks it up (every 2 s) and the station starts degrading.
# MAGIC 3. Watch the risk score in **Delta** (`pdm_core.station_risk_scores`) and in **Postgres** (`pdm_live.station_risk_scores`)
# MAGIC    every 15 s until the station is HIGH in Postgres, where the app reads it.
# MAGIC 4. Create a P1 work order in Lakebase, then complete it, which writes a `repair` command.
# MAGIC 5. Watch the station return to NORMAL. A prevented failure: the station never goes DOWN.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import time, datetime
spark.sql(f"USE CATALOG {CATALOG}")
conn = pg()
ME = w.current_user.me().user_name
utc = lambda: datetime.datetime.now(datetime.timezone.utc)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Pick a healthy CNC mill (bearing wear) and inject the fault

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Watch Delta and Postgres until the station is HIGH where the app reads it

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Act: work order, then complete it (writes a repair command)

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Recovery

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Summary from the system of record

# COMMAND ----------

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
