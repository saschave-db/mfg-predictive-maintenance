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
