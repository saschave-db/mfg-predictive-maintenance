"""Genie agent definition as code: sources, instructions, example SQL, sample questions, benchmarks."""
import hashlib
import json


def _id(text: str) -> str:
    """Deterministic 32-hex id so re-deploys produce stable, diffable configs."""
    return hashlib.md5(text.encode()).hexdigest()


TITLE = "Plant Maintenance Agent"
DESCRIPTION = ("Volta Industrial (Tier-1 EV battery enclosure supplier): ask about live failure risk, OEM delivery "
               "exposure, maintenance history (failures, repairs, downtime, cost) and work orders across Plant North, "
               "South and East. Synthetic demo data; time is compressed.")

INSTRUCTIONS = """\
You are a maintenance planning assistant for Volta Industrial, a Tier-1 supplier of aluminum EV battery enclosures.
It runs three plants (Plant North = PLT-N, Plant South = PLT-S, Plant East = PLT-E),
each with lines A-D and 8 stations per line (station ids like PLT-N-A01).

Time is compressed in this demo: 1 demo minute is about 1 real operating hour. The risk horizon is 5 minutes (about one shift).

Where to find answers:
- "Now", "currently", "right now", "at the moment": use pdm_core.station_health_current (one row per station, latest risk).
  failure_probability is P(station needs maintenance within the horizon). Show it as a percentage.
  risk_band: NORMAL (<40%), ELEVATED (40-70%), HIGH (>=70%), DOWN (station stopped).
- Risk trends or risk over a time range: use the metric view pdm_ops.station_risk_metrics and filter on `Score Time`.
- Failures, repairs, downtime, MTTR, parts cost, preventive share: use the metric view pdm_ops.maintenance_metrics.
- Work orders (backlog, priorities, completion): use pdm_ops.work_order_metrics; for lists of individual work orders use pdm_ops.work_orders_current.
Plant names differ by source: the metric views' Plant dimension holds names ('Plant North', 'Plant South',
'Plant East'); station_health_current and work_orders_current use codes in plant_id ('PLT-N', 'PLT-S', 'PLT-E').
Always query metric views with MEASURE(`Measure Name`) and GROUP BY the dimensions; never SELECT * from a metric view.
OEM customers, vehicle programs, just-in-sequence (JIS) buffers, line-stop charges, chargebacks or "delivery exposure":
use pdm_ops.oem_delivery_exposure (one row per line). exposure_usd_if_fails is the contract charge if the riskiest station
on the line fails now; risk_weighted_exposure_usd weights it by the failure probability. Rank lines or OEMs by
risk_weighted_exposure_usd unless the user asks for the unweighted exposure.
When asked "why" a station is at risk, report top_signal and top_signal_deviation_pct from station_health_current.
"""


def sources(catalog: str) -> dict:
    return {
        "tables": sorted([
            {"identifier": f"{catalog}.pdm_core.station_health_current",
             "column_configs": sorted([
                 {"column_name": "risk_band", "enable_format_assistance": True, "enable_entity_matching": True},
                 {"column_name": "station_type", "enable_format_assistance": True, "enable_entity_matching": True},
                 {"column_name": "plant_id", "enable_format_assistance": True, "enable_entity_matching": True,
                  "description": ["PLT-N = Plant North, PLT-S = Plant South, PLT-E = Plant East"]},
                 {"column_name": "top_signal", "enable_entity_matching": True,
                  "synonyms": ["driver", "anomalous sensor", "reason"]},
                 {"column_name": "failure_probability", "synonyms": ["risk", "maintenance probability"]},
             ], key=lambda c: c["column_name"])},
            {"identifier": f"{catalog}.pdm_ops.oem_delivery_exposure",
             "column_configs": sorted([
                 {"column_name": "oem_customer", "enable_format_assistance": True, "enable_entity_matching": True,
                  "synonyms": ["OEM", "customer", "automaker"]},
                 {"column_name": "vehicle_program", "enable_format_assistance": True, "enable_entity_matching": True,
                  "synonyms": ["program", "vehicle", "model"]},
                 {"column_name": "risk_weighted_exposure_usd",
                  "synonyms": ["delivery exposure", "chargeback exposure", "line-stop exposure"]},
             ], key=lambda c: c["column_name"])},
            {"identifier": f"{catalog}.pdm_ops.work_orders_current"},
        ], key=lambda t: t["identifier"]),
        "metric_views": sorted([
            {"identifier": f"{catalog}.pdm_ops.maintenance_metrics"},
            {"identifier": f"{catalog}.pdm_ops.station_risk_metrics"},
            {"identifier": f"{catalog}.pdm_ops.work_order_metrics"},
        ], key=lambda t: t["identifier"]),
    }


SAMPLE_QUESTIONS = [
    "Which stations need maintenance soon?",
    "Why is the riskiest station at risk?",
    "Which station types fail most often and what is their MTTR?",
    "How many open work orders do we have by priority?",
    "Which OEM programs are exposed to a line stop right now?",
]


def example_sqls(c: str) -> list[tuple[str, str]]:
    return [
        ("Which stations are at high risk right now?",
         f"SELECT station_id, plant_id, station_type, ROUND(failure_probability * 100, 1) AS risk_pct, top_signal, "
         f"top_signal_deviation_pct FROM {c}.pdm_core.station_health_current WHERE risk_band = 'HIGH' "
         f"ORDER BY failure_probability DESC"),
        ("What is the MTTR and failure count by station type?",
         f"SELECT `Station Type`, MEASURE(`Failures`) AS failures, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min "
         f"FROM {c}.pdm_ops.maintenance_metrics GROUP BY ALL ORDER BY failures DESC"),
        ("How did average risk develop per plant over the last 15 minutes?",
         f"SELECT Plant, `Score Minute`, MEASURE(`Avg Failure Probability`) AS avg_risk "
         f"FROM {c}.pdm_ops.station_risk_metrics WHERE `Score Time` > current_timestamp() - INTERVAL 15 MINUTES "
         f"GROUP BY ALL ORDER BY Plant, `Score Minute`"),
        ("Which OEM customer has the highest delivery exposure right now?",
         f"SELECT oem_customer, SUM(risk_weighted_exposure_usd) AS risk_weighted_exposure_usd, "
         f"SUM(high_risk_stations) AS high_risk_stations FROM {c}.pdm_ops.oem_delivery_exposure "
         f"GROUP BY ALL ORDER BY risk_weighted_exposure_usd DESC"),
        ("How many open work orders are there per plant?",
         f"SELECT Plant, MEASURE(`Open Work Orders`) AS open_work_orders FROM {c}.pdm_ops.work_order_metrics "
         f"GROUP BY ALL ORDER BY open_work_orders DESC"),
    ]


def benchmarks(c: str) -> list[tuple[str, str]]:
    hc = f"{c}.pdm_core.station_health_current"
    mm = f"{c}.pdm_ops.maintenance_metrics"
    ox = f"{c}.pdm_ops.oem_delivery_exposure"
    return [
        ("How many stations are at high risk right now?",
         f"SELECT count(*) AS high_risk_stations FROM {hc} WHERE risk_band = 'HIGH'"),
        ("How many stations are currently down?",
         f"SELECT count(*) AS stations_down FROM {hc} WHERE risk_band = 'DOWN'"),
        ("What are the 5 stations with the highest failure probability right now?",
         f"SELECT station_id FROM {hc} ORDER BY failure_probability DESC LIMIT 5"),
        ("Which station type had the most failures?",
         f"SELECT `Station Type`, MEASURE(`Failures`) AS failures FROM {mm} GROUP BY ALL ORDER BY failures DESC LIMIT 1"),
        ("What is the mean time to repair in minutes for each plant?",
         f"SELECT Plant, MEASURE(`Mean Time To Repair Minutes`) AS mttr_min FROM {mm} GROUP BY ALL ORDER BY Plant"),
        ("Which failure mode caused the most downtime?",
         f"SELECT `Failure Mode`, MEASURE(`Downtime Minutes`) AS downtime_min FROM {mm} "
         f"WHERE `Failure Mode` IS NOT NULL GROUP BY ALL ORDER BY downtime_min DESC LIMIT 1"),
        ("What is the total parts cost per plant?",
         f"SELECT Plant, MEASURE(`Parts Cost USD`) AS parts_cost_usd FROM {mm} GROUP BY ALL ORDER BY Plant"),
        ("What share of repairs were preventive for each station type?",
         f"SELECT `Station Type`, MEASURE(`Preventive Share`) AS preventive_share FROM {mm} GROUP BY ALL ORDER BY `Station Type`"),
        ("How many failures did Plant North have?",
         f"SELECT MEASURE(`Failures`) AS failures FROM {mm} WHERE Plant = 'Plant North'"),
        ("List the stations on line PLT-S-B with their current risk band.",
         f"SELECT station_id, risk_band FROM {hc} WHERE line_id = 'PLT-S-B' ORDER BY station_id"),
        ("Which line has the highest risk-weighted OEM delivery exposure right now, and which OEM program does it supply?",
         f"SELECT line_id, vehicle_program FROM {ox} ORDER BY risk_weighted_exposure_usd DESC LIMIT 1"),
        ("What is the JIS buffer in minutes for each line supplying Nordvik Motors?",
         f"SELECT line_id, jis_buffer_min FROM {ox} WHERE oem_customer = 'Nordvik Motors' ORDER BY line_id"),
    ]


def build_serialized_space(catalog: str) -> str:
    bench = benchmarks(catalog)
    payload = {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": _id("sq:" + q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
        "data_sources": sources(catalog),
        "instructions": {
            "text_instructions": [{"id": _id("instructions"), "content": [INSTRUCTIONS]}],
            "example_question_sqls": sorted(
                [{"id": _id("ex:" + q), "question": [q], "sql": [s]} for q, s in example_sqls(catalog)],
                key=lambda x: x["id"]),
        },
        "benchmarks": {"questions": sorted(
            [{"id": _id("bm:" + q), "question": [q], "answer": [{"format": "SQL", "content": [s]}]} for q, s in bench],
            key=lambda x: x["id"])},
    }
    return json.dumps(payload)
