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
