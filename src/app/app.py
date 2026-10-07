"""Plant Health Live: FastAPI backend for the predictive maintenance demo.

Reads live risk state from Lakebase synced tables, writes work orders and fault-injection commands to
Lakebase OLTP tables, re-scores stations through Model Serving, and embeds a Genie agent.
All data is synthetic.
"""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db

LIVE = os.environ.get("LIVE_SCHEMA", "pdm_live")
OPS = os.environ.get("OPS_SCHEMA", "pdm_ops")
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "pdm-station-risk")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
# Latest risk row per station, straight from the continuously synced score history (PK station_id, window_end).
# Skips the AUTO CDC current-state hop on the latency path; the PK index makes DISTINCT ON cheap.
LATEST = (f"(SELECT DISTINCT ON (station_id) * FROM {LIVE}.station_risk_scores "
          f"WHERE window_end > now() - interval '10 minutes' ORDER BY station_id, window_end DESC) AS latest")
FEATURE_SENSORS = ["vibration_rms", "bearing_temp_c", "motor_current_a", "spindle_rpm",
                   "hydraulic_pressure_bar", "acoustic_db", "cycle_time_s"]
FEATURE_COLUMNS = [f"{s}_{a}" for s in FEATURE_SENSORS for a in ("mean", "std", "max", "min")]


@asynccontextmanager
async def lifespan(_):
    db.pool.open(wait=True, timeout=60)
    yield
    db.pool.close()


app = FastAPI(title="Plant Health Live", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


def user_of(request: Request) -> str:
    return request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-user") or "demo-user"


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/stations")
def stations():
    t0 = time.perf_counter()
    rows = db.query(f"""
        SELECT station_id, plant_id, line_id, station_type, criticality, failure_probability, risk_band,
               top_signal, top_signal_deviation_pct, window_end, last_reading_ts, scored_at,
               avg_vibration_rms, avg_bearing_temp_c, avg_motor_current_a, avg_hydraulic_pressure_bar
        FROM {LATEST} ORDER BY station_id""")
    now = datetime.now(timezone.utc)
    open_wo = {r["station_id"]: r["n"] for r in db.query(
        f"SELECT station_id, count(*) AS n FROM {OPS}.work_orders WHERE status IN ('open','in_progress') GROUP BY 1")}
    freshest = max((r["last_reading_ts"] for r in rows if r["last_reading_ts"]), default=None)
    for r in rows:
        r["open_work_orders"] = open_wo.get(r["station_id"], 0)
    return {
        "stations": rows,
        "as_of": now.isoformat(),
        # Sensor-to-screen freshness: how old is the newest reading reflected in the risk state?
        "data_age_s": round((now - freshest.replace(tzinfo=timezone.utc)).total_seconds(), 1) if freshest else None,
        "lakebase_query_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


@app.get("/api/stations/{station_id}/history")
def history(station_id: str, minutes: int = 15):
    rows = db.query(f"""
        SELECT window_end, failure_probability, risk_band, top_signal, avg_vibration_rms, avg_bearing_temp_c,
               avg_motor_current_a, avg_hydraulic_pressure_bar, avg_acoustic_db, avg_cycle_time_s
        FROM {LIVE}.station_risk_scores
        WHERE station_id = %s AND window_end > now() - make_interval(mins => %s)
        ORDER BY window_end""", (station_id, minutes))
    return {"station_id": station_id, "points": rows}


class Inject(BaseModel):
    station_id: str
    failure_mode: str | None = None


@app.post("/api/inject")
def inject(body: Inject, request: Request):
    r = db.query(f"""INSERT INTO {OPS}.sim_commands (command, station_id, failure_mode, requested_by)
                     VALUES ('inject_fault', %s, %s, %s) RETURNING command_id, requested_at""",
                 (body.station_id, body.failure_mode, user_of(request)))
    return r[0]


class WorkOrderIn(BaseModel):
    station_id: str
    priority: str = Field("P2", pattern="^P[123]$")
    description: str = ""
    assigned_technician_id: str | None = None


@app.post("/api/work_orders")
def create_work_order(body: WorkOrderIn, request: Request):
    st = db.query(f"""SELECT plant_id, line_id, failure_probability, risk_band, top_signal
                      FROM {LATEST} WHERE station_id = %s""", (body.station_id,))
    if not st:
        raise HTTPException(404, "unknown station")
    s = st[0]
    return db.query(f"""
        INSERT INTO {OPS}.work_orders (station_id, plant_id, line_id, priority, failure_probability, risk_band,
                                       top_signal, description, assigned_technician_id, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
        (body.station_id, s["plant_id"], s["line_id"], body.priority, s["failure_probability"], s["risk_band"],
         s["top_signal"], body.description or f"Predicted {s['top_signal']} issue", body.assigned_technician_id,
         user_of(request)))[0]


@app.get("/api/work_orders")
def list_work_orders(limit: int = 50):
    return db.query(f"SELECT * FROM {OPS}.work_orders ORDER BY created_at DESC LIMIT %s", (limit,))


@app.post("/api/work_orders/{work_order_id}/complete")
def complete_work_order(work_order_id: int, request: Request):
    wo = db.query(f"""UPDATE {OPS}.work_orders SET status = 'completed', completed_at = now(), updated_at = now()
                      WHERE work_order_id = %s RETURNING *""", (work_order_id,))
    if not wo:
        raise HTTPException(404, "unknown work order")
    # Closing the loop: the repair resets the station in the simulator.
    db.query(f"""INSERT INTO {OPS}.sim_commands (command, station_id, requested_by)
                 VALUES ('repair', %s, %s)""", (wo[0]["station_id"], user_of(request)))
    return wo[0]


class WhatIf(BaseModel):
    station_id: str
    sensor: str = "vibration_rms"
    change_pct: float = 20.0


@app.post("/api/whatif")
def whatif(body: WhatIf):
    """Re-score the station's latest window through Model Serving, with one sensor shifted by change_pct."""
    if body.sensor not in FEATURE_SENSORS:
        raise HTTPException(400, "unknown sensor")
    cols = ", ".join(FEATURE_COLUMNS)
    rows = db.query(f"SELECT {cols} FROM {LATEST} WHERE station_id = %s", (body.station_id,))
    if not rows:
        raise HTTPException(404, "unknown station")
    base = {k: float(v) for k, v in rows[0].items()}
    shifted = dict(base)
    for agg in ("mean", "max", "min"):
        shifted[f"{body.sensor}_{agg}"] = base[f"{body.sensor}_{agg}"] * (1 + body.change_pct / 100)
    # Call through the endpoint's AI Gateway (usage tracking -> system.serving.endpoint_usage).
    path = f"/serving-endpoints/{SERVING_ENDPOINT}/invocations"
    t0 = time.perf_counter()
    resp = db.w.api_client.do("POST", path, body={"dataframe_records": [base, shifted]})
    return {
        "station_id": body.station_id, "sensor": body.sensor, "change_pct": body.change_pct,
        "current_probability": round(float(resp["predictions"][0]), 4),
        "scenario_probability": round(float(resp["predictions"][1]), 4),
        "serving_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "endpoint": SERVING_ENDPOINT,
        "gateway_url": db.w.config.host.rstrip("/") + path,
    }


class Ask(BaseModel):
    question: str
    conversation_id: str | None = None


@app.post("/api/genie")
def genie(body: Ask):
    if not GENIE_SPACE_ID:
        raise HTTPException(503, "Genie space not configured")
    g = db.w.genie
    msg = (g.create_message_and_wait(GENIE_SPACE_ID, body.conversation_id, body.question) if body.conversation_id
           else g.start_conversation_and_wait(GENIE_SPACE_ID, body.question))
    out = {"conversation_id": msg.conversation_id, "message_id": msg.message_id,
           "status": str(msg.status.value if msg.status else ""), "text": None, "sql": None, "columns": [], "rows": []}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["text"] = att.text.content
        if att.query:
            out["sql"] = att.query.query
            out["text"] = out["text"] or att.query.description
            res = g.get_message_attachment_query_result(GENIE_SPACE_ID, msg.conversation_id, msg.message_id,
                                                        att.attachment_id)
            sr = res.statement_response
            if sr and sr.manifest and sr.result:
                out["columns"] = [c.name for c in sr.manifest.schema.columns]
                out["rows"] = (sr.result.data_array or [])[:50]
    return out


@app.get("/api/health")
def health():
    t0 = time.perf_counter()
    db.query("SELECT 1")
    return {"ok": True, "lakebase_roundtrip_ms": round((time.perf_counter() - t0) * 1000, 1)}


WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
CATALOG = os.environ.get("CATALOG", "serverless_stable_am1uc2_catalog")


@app.get("/api/governance/technicians")
def governance_technicians():
    """Query technicians through the SQL warehouse as the app's service principal (a non-owner identity).

    Unity Catalog applies the row filter (pdm_ops.plant_access grants this SP Plant North only) and the PII masks
    (the SP is not in pdm_supervisors). The statement id lets reviewers find the query in system.query.history.
    """
    if not WAREHOUSE_ID:
        raise HTTPException(503, "warehouse not configured")
    sql = (f"SELECT current_user() AS executed_as, technician_id, full_name, home_plant_id, email, phone "
           f"FROM {CATALOG}.pdm_raw.technicians ORDER BY technician_id")
    t0 = time.perf_counter()
    st = db.w.statement_execution.execute_statement(statement=sql, warehouse_id=WAREHOUSE_ID, wait_timeout="50s")
    cols = [c.name for c in st.manifest.schema.columns] if st.manifest else []
    rows = (st.result.data_array or []) if st.result else []
    return {"statement_id": st.statement_id, "state": st.status.state.value, "sql": sql,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "columns": cols, "row_count": len(rows),
            "plants_visible": sorted({r[3] for r in rows}), "rows": rows}
