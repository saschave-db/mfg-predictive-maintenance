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
