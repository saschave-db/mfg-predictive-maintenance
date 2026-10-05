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
    df = readings.join(F.broadcast(sm), ["station_id"], "inner")
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
