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
