# Executed notebook: 01_backfill_history

Exported from Databricks job run `552116966031272` (task `backfill`, task run `315418415693122`).

Result: **SUCCESS** · start 2026-10-05T22:28:16.527000+00:00 · end 2026-10-05T22:37:55.283000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/327188914455836/run/552116966031272


# 01 · Backfill labeled history
Runs the **same physics** as the live Zerobus producer over a past window, one simulation per production
line in parallel (`applyInPandas`). Output:
* `pdm_ml.history_readings`: 1 Hz telemetry plus ground-truth time-to-failure (training only, never live)
* `pdm_raw.maintenance_events_history`: failures and repairs with technician, downtime, cost

Time is compressed: one demo minute is about one real operating hour. All data is synthetic.

```python
dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
dbutils.widgets.text("history_hours", "24")
CATALOG = dbutils.widgets.get("catalog")
HOURS = float(dbutils.widgets.get("history_hours"))

import os, sys
sys.path.append(os.path.abspath(".."))
import time, zlib
import numpy as np
import pandas as pd
from pyspark.sql import functions as F, types as T
from pdm.config import SENSORS
from pdm.physics import Fleet, build_station_master

N_SECONDS = int(HOURS * 3600)
T_END = float(int(time.time()) // 3600 * 3600 - 3600)  # end one hour before now, aligned
T_START = T_END - N_SECONDS
print(f"history window: {pd.Timestamp(T_START, unit='s')} -> {pd.Timestamp(T_END, unit='s')} UTC, {N_SECONDS:,} s per station")
```

Output:

```text
history window: 2026-10-04 21:00:00 -> 2026-10-05 21:00:00 UTC, 86,400 s per station
```

```python
stations = build_station_master()
station_by_line = {}
for s in stations:
    station_by_line.setdefault(s["line_id"], []).append(s)
lines_df = spark.createDataFrame([(l,) for l in station_by_line], "line_id string")

reading_schema = T.StructType(
    [T.StructField("station_id", T.StringType()), T.StructField("ts", T.TimestampType())]
    + [T.StructField(s, T.DoubleType()) for s in SENSORS]
    + [T.StructField("ttf_s", T.DoubleType()), T.StructField("true_failure_mode", T.StringType())]
)
event_schema = T.StructType([
    T.StructField("station_id", T.StringType()), T.StructField("event_ts", T.TimestampType()),
    T.StructField("event_type", T.StringType()), T.StructField("failure_mode", T.StringType()),
])


def simulate(line_id, want):
    line_stations = station_by_line[line_id]
    fleet = Fleet(line_stations, seed=zlib.crc32(line_id.encode()), t0=T_START, auto_preventive_prob=0.2)
    n = fleet.n
    cols = {s: np.empty(N_SECONDS * n) for s in SENSORS}
    ttf = np.empty(N_SECONDS * n)
    mode = np.empty(N_SECONDS * n, dtype=object)
    events = []
    for k in range(N_SECONDS):
        t = T_START + k
        r, evs = fleet.step(t)
        sl = slice(k * n, (k + 1) * n)
        for s in SENSORS:
            cols[s][sl] = r[s]
        ttf[sl] = fleet.ttf_seconds(t)
        mode[sl] = fleet.mode
        for e in evs:
            events.append((e["station_id"], pd.Timestamp(t, unit="s"), e["event_type"], e["failure_mode"]))
    if want == "events":
        return pd.DataFrame(events, columns=["station_id", "event_ts", "event_type", "failure_mode"])
    out = pd.DataFrame({
        "station_id": np.tile(fleet.ids, N_SECONDS),
        "ts": pd.to_datetime(np.repeat(T_START + np.arange(N_SECONDS), n), unit="s"),
        **cols,
        "ttf_s": np.where(np.isinf(ttf), np.nan, ttf),
        "true_failure_mode": np.where(mode == "", None, mode),
    })
    return out


readings = lines_df.groupBy("line_id").applyInPandas(lambda pdf: simulate(pdf.line_id[0], "readings"), reading_schema)
events = lines_df.groupBy("line_id").applyInPandas(lambda pdf: simulate(pdf.line_id[0], "events"), event_schema)
```

```python
t0 = time.time()
(readings.write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{CATALOG}.pdm_ml.history_readings"))
spark.sql(f"COMMENT ON TABLE {CATALOG}.pdm_ml.history_readings IS "
          "'Simulated 1 Hz history with ground-truth ttf_s (seconds to projected failure). Training only. Synthetic.'")
print(f"history_readings written in {time.time() - t0:.0f}s")
display(spark.sql(f"""
SELECT count(*) AS rows, count(DISTINCT station_id) AS stations, min(ts) AS first_ts, max(ts) AS last_ts,
       round(avg(CASE WHEN ttf_s <= 300 THEN 1 ELSE 0 END) * 100, 2) AS pct_rows_within_5min_of_failure
FROM {CATALOG}.pdm_ml.history_readings"""))
```

Output:

```text
history_readings written in 270s
```

Output:

| rows | stations | first_ts | last_ts | pct_rows_within_5min_of_failure |
|---|---|---|---|---|
| 8294400 | 96 | 2026-10-04T21:00:00.000Z | 2026-10-05T20:59:59.000Z | 5.43 |

## Maintenance log (CMMS-style)
Failures and repairs, enriched with technician, downtime and cost. Degradation onsets are hidden ground truth
and are not part of the maintenance log.

```python
ev = events.filter("event_type != 'degradation_onset'").toPandas()
techs = spark.table(f"{CATALOG}.pdm_raw.technicians").toPandas()
plant_of = {s["station_id"]: s["plant_id"] for s in stations}
rng = np.random.default_rng(3)
rows = []
for r in ev.sort_values("event_ts").itertuples():
    plant = plant_of[r.station_id]
    tech = techs[techs.home_plant_id == plant].sample(1, random_state=int(rng.integers(1e9))).iloc[0]
    corrective = r.event_type == "corrective_repair"
    rows.append(dict(
        event_id=f"H-{r.station_id}-{int(r.event_ts.timestamp())}-{r.event_type[:4]}",
        station_id=r.station_id, event_ts=r.event_ts, event_type=r.event_type, failure_mode=r.failure_mode,
        technician_id=None if r.event_type == "failure" else tech.technician_id,
        downtime_min=float(rng.uniform(45, 180)) if corrective else (float(rng.uniform(15, 40)) if r.event_type == "preventive_repair" else 0.0),
        parts_cost_usd=float(rng.uniform(2500, 12000)) if corrective else (float(rng.uniform(300, 1500)) if r.event_type == "preventive_repair" else 0.0),
        source="history",
    ))
mlog = spark.createDataFrame(pd.DataFrame(rows))
(mlog.write.mode("overwrite").option("overwriteSchema", "true")
 .saveAsTable(f"{CATALOG}.pdm_raw.maintenance_events_history"))
spark.sql(f"COMMENT ON TABLE {CATALOG}.pdm_raw.maintenance_events_history IS "
          "'Historical maintenance log: failures, corrective and preventive repairs (synthetic, compressed time).'")
display(spark.sql(f"""
SELECT m.event_type, s.station_type, count(*) AS events, round(sum(downtime_min)) AS downtime_min,
       round(sum(parts_cost_usd)) AS parts_cost_usd
FROM {CATALOG}.pdm_raw.maintenance_events_history m JOIN {CATALOG}.pdm_raw.station_master s USING (station_id)
GROUP BY ALL ORDER BY ALL"""))
```

Output:

| event_type | station_type | events | downtime_min | parts_cost_usd |
|---|---|---|---|---|
| corrective_repair | cnc_mill | 295 | 33983.0 | 2107870.0 |
| corrective_repair | conveyor | 124 | 13890.0 | 908278.0 |
| corrective_repair | press | 280 | 31034.0 | 2009251.0 |
| corrective_repair | robot_arm | 137 | 14913.0 | 995787.0 |
| corrective_repair | welder | 260 | 29251.0 | 1869504.0 |
| failure | cnc_mill | 296 | 0.0 | 0.0 |
| failure | conveyor | 124 | 0.0 | 0.0 |
| failure | press | 280 | 0.0 | 0.0 |
| failure | robot_arm | 137 | 0.0 | 0.0 |
| failure | welder | 260 | 0.0 | 0.0 |
| preventive_repair | cnc_mill | 66 | 1847.0 | 57196.0 |
| preventive_repair | conveyor | 28 | 809.0 | 24100.0 |
| preventive_repair | press | 75 | 2113.0 | 68891.0 |
| preventive_repair | robot_arm | 29 | 838.0 | 26759.0 |
| preventive_repair | welder | 70 | 1825.0 | 56487.0 |
