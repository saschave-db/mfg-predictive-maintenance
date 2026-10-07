# Executed notebook: E09_source_integrity

Exported from Databricks job run `994447175034582` (task `E09_source_integrity`, task run `684494378934229`).

Result: **SUCCESS** · start 2026-10-07T23:14:02.443000+00:00 · end 2026-10-07T23:14:20.500000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


# E09 · Source integrity: the code that runs is the code in the repo

`evidence/source_snapshot/` holds a byte-identical copy of the pipeline, shared feature/physics code, simulator and
pipeline config, with `SHA256SUMS` (written by `tools/snapshot_source.py`).

**What this notebook proves.**
1. The running SDP pipeline's libraries point to the bundle-deployed files.
2. The SHA-256 of every **deployed** file equals the committed checksum (and the committed snapshot copy).
3. The full deployed pipeline source, printed below as text.

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
import hashlib, os
ROOT = os.path.abspath("../../..")  # bundle files root in the workspace
print("deployed bundle root:", ROOT)
```

Output:

```text
deployed bundle root: /Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files
```

## 1 · Pipeline libraries as configured on the running pipeline

```python
p = w.pipelines.get(PIPELINE_ID)
libs = [l.file.path for l in p.spec.libraries]
print("pipeline:", p.name, "| state:", p.state.value, "| continuous:", p.spec.continuous)
for l in libs:
    print("  library:", l, "| under deployed root:", l.startswith(ROOT.replace("/Workspace", "")) or l.startswith(ROOT))
```

Output:

```text
pipeline: pdm_live_pipeline | state: RUNNING | continuous: True
  library: /Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src/pipeline/01_sensor_readings_clean.py | under deployed root: True
  library: /Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src/pipeline/02_station_risk_scores.py | under deployed root: True
  library: /Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src/pipeline/03_station_health_current.py | under deployed root: True
  library: /Workspace/Users/sascha.vetter@databricks.com/.bundle/mfg-predictive-maintenance/demo/files/src/pipeline/04_maintenance_events.py | under deployed root: True
```

## 2 · SHA-256 of deployed files vs committed checksums vs committed snapshot

```python
sums = {}
for line in open(os.path.join(ROOT, "evidence/source_snapshot/SHA256SUMS")).read().splitlines():
    h, f = line.split("  ", 1)
    sums[f] = h
sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
rows = []
for f, expected in sorted(sums.items()):
    deployed = sha(os.path.join(ROOT, f))
    snapshot = sha(os.path.join(ROOT, "evidence/source_snapshot", f))
    rows.append((f, deployed[:16], expected[:16], snapshot[:16], deployed == expected == snapshot))
display(spark.createDataFrame(rows, "file string, deployed_sha256 string, committed_sha256 string, snapshot_sha256 string, identical boolean"))
print("ALL IDENTICAL" if all(r[-1] for r in rows) else "MISMATCH FOUND")
```

Output:

| file | deployed_sha256 | committed_sha256 | snapshot_sha256 | identical |
|---|---|---|---|---|
| resources/pipeline.yml | be17f976a535d73e | be17f976a535d73e | be17f976a535d73e | True |
| src/pdm/__init__.py | e3b0c44298fc1c14 | e3b0c44298fc1c14 | e3b0c44298fc1c14 | True |
| src/pdm/config.py | fdbb712446294c2b | fdbb712446294c2b | fdbb712446294c2b | True |
| src/pdm/features.py | e599eb4f32a94daf | e599eb4f32a94daf | e599eb4f32a94daf | True |
| src/pdm/physics.py | c69618599cb93d07 | c69618599cb93d07 | c69618599cb93d07 | True |
| src/pipeline/01_sensor_readings_clean.py | 217fb117f1a001b7 | 217fb117f1a001b7 | 217fb117f1a001b7 | True |
| src/pipeline/02_station_risk_scores.py | 7783a6ba6b0ca9fb | 7783a6ba6b0ca9fb | 7783a6ba6b0ca9fb | True |
| src/pipeline/03_station_health_current.py | 3b0149c23ec384b9 | 3b0149c23ec384b9 | 3b0149c23ec384b9 | True |
| src/pipeline/04_maintenance_events.py | 35714378c3c0483b | 35714378c3c0483b | 35714378c3c0483b | True |
| src/pipeline/_common.py | 0f7cc3223fa2ef04 | 0f7cc3223fa2ef04 | 0f7cc3223fa2ef04 | True |
| src/simulator/zerobus_producer.py | 4dd68f2cf112d27e | 4dd68f2cf112d27e | 4dd68f2cf112d27e | True |

Output:

```text
ALL IDENTICAL
```

## 3 · Full deployed pipeline source

```python
for f in sorted(k for k in sums if k.startswith("src/pipeline/") or k == "src/pdm/features.py" or k == "resources/pipeline.yml"):
    print(f"{'=' * 100}\n# {f}  sha256={sums[f]}\n{'=' * 100}")
    print(open(os.path.join(ROOT, f)).read())
```

Output:

```text
====================================================================================================
# resources/pipeline.yml  sha256=be17f976a535d73e51cd5b75fb78af81139cb1d9e100d8544fa34cac54676689
====================================================================================================
resources:
  pipelines:
    pdm_live:
      name: pdm_live_pipeline
      catalog: ${var.catalog}
      schema: pdm_core
      serverless: true
      continuous: true
      photon: true
      channel: CURRENT
      root_path: ../src/pipeline
      libraries:
        - file:
            path: ../src/pipeline/01_sensor_readings_clean.py
        - file:
            path: ../src/pipeline/02_station_risk_scores.py
        - file:
            path: ../src/pipeline/03_station_health_current.py
        - file:
            path: ../src/pipeline/04_maintenance_events.py
      configuration:
        pdm.catalog: ${var.catalog}
        pdm.source_path: ${workspace.file_path}/src
      environment:
        dependencies:
          - scikit-learn==1.7.2
          - mlflow>=3.1

====================================================================================================
# src/pdm/features.py  sha256=e599eb4f32a94daf4c7f5448d30c649123370b4ed0ff93ae4c4a60ff21908122
====================================================================================================
"""Single feature definition shared by model training (batch) and the SDP pipeline (streaming).

Sensors are normalized by the station-type nominal, so one model serves every station type.
"""
from pyspark.sql import DataFrame, functions as F

from pdm.config import SENSORS, WINDOW_DURATION, WINDOW_SLIDE

FEATURE_COLUMNS = [f"{s}_{agg}" for s in SENSORS for agg in ("mean", "std", "max", "min")]


def normalize(readings: DataFrame, station_master: DataFrame) -> DataFrame:
    """Join nominal values and add <sensor>_n = value / nominal."""
    nom_cols = [f"nom_{s}" for s in SENSORS]
    sm = station_master.select("station_id", "plant_id", "line_id", "station_type", "criticality", *nom_cols)
    df = readings.drop("plant_id", "line_id").join(F.broadcast(sm), ["station_id"], "inner")
    for s in SENSORS:
        df = df.withColumn(f"{s}_n", F.col(s) / F.col(f"nom_{s}"))
    return df.drop(*nom_cols)


def window_features(normalized: DataFrame, extra_aggs: list | None = None) -> DataFrame:
    """Sliding-window aggregates per station. Input must have ts and <sensor>_n columns."""
    aggs = []
    for s in SENSORS:
        c = F.col(f"{s}_n")
        aggs += [
            F.avg(c).alias(f"{s}_mean"),
            F.coalesce(F.stddev(c), F.lit(0.0)).alias(f"{s}_std"),
            F.max(c).alias(f"{s}_max"),
            F.min(c).alias(f"{s}_min"),
        ]
    aggs += [
        F.count(F.lit(1)).alias("n_readings"),
        F.max("ts").alias("last_reading_ts"),
        # Raw (un-normalized) means for display in the app and Genie.
        *[F.avg(s).alias(f"avg_{s}") for s in SENSORS],
    ]
    aggs += extra_aggs or []
    return (
        normalized
        .groupBy("station_id", "plant_id", "line_id", "station_type", "criticality",
                 F.window("ts", WINDOW_DURATION, WINDOW_SLIDE).alias("w"))
        .agg(*aggs)
        .withColumn("window_start", F.col("w.start"))
        .withColumn("window_end", F.col("w.end"))
        .drop("w")
    )


def top_deviating_signal(df: DataFrame) -> DataFrame:
    """Simple explanation: sensor whose window mean deviates most from nominal (1.0)."""
    dev = F.array(*[
        F.struct(F.abs(F.col(f"{s}_mean") - 1.0).alias("dev"), F.lit(s).alias("sensor")) for s in SENSORS
    ])
    return df.withColumn("top_signal", F.array_max(dev)["sensor"]).withColumn(
        "top_signal_deviation_pct", F.round(F.array_max(dev)["dev"] * 100, 1)
    )

====================================================================================================
# src/pipeline/01_sensor_readings_clean.py  sha256=217fb117f1a001b7177f09a158149b6e7b3321ec252c398f756ed42abd7bc259
====================================================================================================
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from _common import RAW, spark
from pdm.features import normalize

VALID = {
    "valid_station": "station_id IS NOT NULL",
    "valid_ts": "ts IS NOT NULL",
    "vibration_in_range": "vibration_rms BETWEEN 0 AND 50",
    "temperature_in_range": "bearing_temp_c BETWEEN -20 AND 250",
    "current_in_range": "motor_current_a BETWEEN 0 AND 1000",
    "pressure_in_range": "hydraulic_pressure_bar BETWEEN 0 AND 400",
}


@dp.table(
    comment="Silver: de-duplicated (Zerobus is at-least-once), validated, normalized 1 Hz telemetry.",
    cluster_by=["station_id"],
)
@dp.expect_all_or_drop(VALID)
@dp.expect("not_from_future", "ts <= current_timestamp() + INTERVAL 1 MINUTE")
def sensor_readings_clean():
    bronze = (
        spark.readStream.table(f"{RAW}.sensor_readings")
        .withWatermark("ts", "30 seconds")
        .dropDuplicatesWithinWatermark(["event_id"])
    )
    return normalize(bronze, spark.read.table(f"{RAW}.station_master")).withColumn(
        "silver_at", F.current_timestamp()
    )

====================================================================================================
# src/pipeline/02_station_risk_scores.py  sha256=7783a6ba6b0ca9fbaed0b55c26a98ee7bd42cb5dbca83ffc34f3c40c70c44d20
====================================================================================================
import mlflow
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from _common import ML, spark
from pdm.config import MODEL_ALIAS, MODEL_NAME, WATERMARK_DELAY
from pdm.features import FEATURE_COLUMNS, top_deviating_signal, window_features

mlflow.set_registry_uri("databricks-uc")
MODEL_URI = f"models:/{ML}.{MODEL_NAME}@{MODEL_ALIAS}"
predict_proba = mlflow.pyfunc.spark_udf(spark, MODEL_URI, result_type="double", env_manager="local")
MIN_READINGS = 110  # same completeness rule as the training set (a full window has 120 readings)


@dp.table(
    comment=("Gold: 2-minute sliding-window features (every 10 s, same definition as training) scored in-stream "
             "with the UC model @champion. Windowing and scoring run in one flow to avoid an extra streaming hop."),
    cluster_by=["station_id"],
    table_properties={"delta.enableChangeDataFeed": "true"},
)
@dp.expect_or_drop("complete_window", f"n_readings >= {MIN_READINGS}")  # dropped windows are counted in the event log
def station_risk_scores():
    silver = spark.readStream.table("sensor_readings_clean").withWatermark("ts", WATERMARK_DELAY)
    feats = window_features(silver).withColumn("features_at", F.current_timestamp())
    scored = feats.withColumn("failure_probability", F.round(predict_proba(*[F.col(c) for c in FEATURE_COLUMNS]), 4))
    scored = top_deviating_signal(scored)
    return scored.select(
        "station_id", "plant_id", "line_id", "station_type", "criticality",
        "window_start", "window_end", "last_reading_ts", "n_readings",
        "failure_probability",
        F.when(F.col("spindle_rpm_mean") < 0.2, "DOWN")
         .when(F.col("failure_probability") >= 0.7, "HIGH")
         .when(F.col("failure_probability") >= 0.4, "ELEVATED")
         .otherwise("NORMAL").alias("risk_band"),
        "top_signal", "top_signal_deviation_pct",
        *[c for c in feats.columns if c.startswith("avg_")],
        *FEATURE_COLUMNS,
        F.lit(MODEL_URI).alias("model_uri"),
        "features_at",
        F.current_timestamp().alias("scored_at"),
    )

====================================================================================================
# src/pipeline/03_station_health_current.py  sha256=3b0149c23ec384b9d771007f101d46774531ed107617c58787abc856ded58637
====================================================================================================
from pyspark import pipelines as dp

from _common import spark  # noqa: F401  (sets sys.path)

dp.create_streaming_table(
    name="station_health_current",
    comment="Gold: latest risk state per station (SCD1 via AUTO CDC). Synced to Lakebase for the app.",
    table_properties={"delta.enableChangeDataFeed": "true"},
)
dp.create_auto_cdc_flow(
    target="station_health_current",
    source="station_risk_scores",
    keys=["station_id"],
    sequence_by="window_end",
    stored_as_scd_type=1,
)

====================================================================================================
# src/pipeline/04_maintenance_events.py  sha256=35714378c3c0483be01c39c9a28c82decd780f651eb105fd6adb5ef67cc01c63
====================================================================================================
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from _common import RAW, spark


@dp.materialized_view(
    comment="Gold: maintenance log (failures, corrective and preventive repairs) with station context.",
)
def maintenance_events():
    ev = spark.read.table(f"{RAW}.maintenance_events_history")
    sm = spark.read.table(f"{RAW}.station_master").select(
        "station_id", "plant_id", "plant_name", "line_id", "station_type", "criticality")
    return ev.join(sm, "station_id").withColumn("event_date", F.to_date("event_ts"))

====================================================================================================
# src/pipeline/_common.py  sha256=0f7cc3223fa2ef04e9d3538ac0d7c48c6e333440453cfa196ce0021b08f245d5
====================================================================================================
"""Pipeline-wide settings. Imported by every pipeline source file."""
import sys

from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()
sys.path.append(spark.conf.get("pdm.source_path"))

CATALOG = spark.conf.get("pdm.catalog")
RAW = f"{CATALOG}.pdm_raw"
ML = f"{CATALOG}.pdm_ml"
```
