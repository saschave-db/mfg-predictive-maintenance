"""End-to-end demo run through the deployed app's API; writes a text timeline as evidence.

App -> Lakebase sim_commands -> simulator -> Zerobus -> SDP (silver, window features, in-stream model)
-> Lakebase synced table -> app. Then work order, Model Serving what-if, Genie, and repair.

Usage: python tools/e2e_demo.py --out evidence/08_app/e2e_fault_injection.md
"""
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone

import requests

APP = "https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com"


def token(profile):
    out = subprocess.run(["databricks", "auth", "token", "--profile", profile, "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["access_token"]


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


ap = argparse.ArgumentParser()
ap.add_argument("--profile", default="fevm-serverless-stable-am1uc2")
ap.add_argument("--out", required=True)
ap.add_argument("--max-wait-s", type=int, default=900)
a = ap.parse_args()
s = requests.Session()
s.headers["Authorization"] = f"Bearer {token(a.profile)}"
md, t_start = [], time.time()


def call(method, path, body=None):
    t0 = time.perf_counter()
    r = s.request(method, APP + path, json=body, timeout=120)
    r.raise_for_status()
    ms = (time.perf_counter() - t0) * 1000
    md.append(f"`{now()}` **{method} {path}** ({ms:.0f} ms)" + (f" body `{json.dumps(body)}`" if body else ""))
    return r.json()


def station(sid):
    d = call("GET", "/api/stations")
    st = next(x for x in d["stations"] if x["station_id"] == sid)
    return d, st


# 1. Pick a healthy welder (overheating) as the target.
d = call("GET", "/api/stations")
target = next(x for x in d["stations"] if x["station_type"] == "welder" and x["risk_band"] == "NORMAL"
              and x["failure_probability"] < 0.1 and not x["open_work_orders"])
sid = target["station_id"]
bands = {}
for x in d["stations"]:
    bands[x["risk_band"]] = bands.get(x["risk_band"], 0) + 1
md.append(f"Fleet before injection: {bands}; data age {d['data_age_s']} s; Lakebase query {d['lakebase_query_ms']} ms. "
          f"Target **{sid}** at {target['failure_probability'] * 100:.1f}% ({target['risk_band']}).")

# 2. Inject the fault from the app (writes Lakebase pdm_ops.sim_commands).
inj = call("POST", "/api/inject", {"station_id": sid, "failure_mode": "overheating"})
injected_at = inj["requested_at"]
md.append(f"Command #{inj['command_id']} queued at {injected_at}.")

# 3. Watch the station until it is HIGH (and keep watching until DOWN or timeout).
md.append("\n| time (UTC) | risk | band | top signal | deviation % | temp °C | current A | window end | data age s |\n|---|---|---|---|---|---|---|---|---|")
first_high, wo = None, None
while time.time() - t_start < a.max_wait_s:
    d = s.get(APP + "/api/stations", timeout=60).json()
    st = next(x for x in d["stations"] if x["station_id"] == sid)
    md.append(f"| {now()} | {st['failure_probability'] * 100:.1f}% | {st['risk_band']} | {st['top_signal']} | "
              f"{st['top_signal_deviation_pct']} | {float(st['avg_bearing_temp_c']):.1f} | {float(st['avg_motor_current_a']):.1f} | "
              f"{st['window_end'][11:19]} | {d['data_age_s']} |")
    print(md[-1], flush=True)
    if st["risk_band"] == "HIGH" and not first_high:
        first_high = now()
        break
    time.sleep(10)
md.append("")

# 4. Act on the alert: work order, what-if via Model Serving, ask Genie.
if first_high:
    wo = call("POST", "/api/work_orders", {"station_id": sid, "priority": "P1",
                                            "description": "E2E test: overheating alert"})
    md.append(f"Work order #{wo['work_order_id']} created: priority {wo['priority']}, risk at creation "
              f"{float(wo['failure_probability']) * 100:.1f}%, top signal {wo['top_signal']}.")
    wi = call("POST", "/api/whatif", {"station_id": sid, "sensor": "bearing_temp_c", "change_pct": -10})
    md.append(f"What-if (bearing temp -10%) via `{wi['endpoint']}`: now {wi['current_probability'] * 100:.1f}% -> "
              f"scenario {wi['scenario_probability'] * 100:.1f}% (serving round trip {wi['serving_latency_ms']} ms).")
    g = call("POST", "/api/genie", {"question": f"Why is station {sid} at risk right now?"})
    md.append(f"Genie answer: {g['text']}\n\nGenie SQL:\n```sql\n{g['sql']}\n```\nGenie rows: `{g['rows'][:3]}`")

    # 5. Complete the work order -> repair command -> station resets.
    done = call("POST", f"/api/work_orders/{wo['work_order_id']}/complete")
    md.append(f"Work order #{done['work_order_id']} completed at {done['completed_at']}; repair command queued.")
    md.append("\n| time (UTC) | risk | band | window end |\n|---|---|---|---|")
    t_rep = time.time()
    while time.time() - t_rep < 300:
        d = s.get(APP + "/api/stations", timeout=60).json()
        st = next(x for x in d["stations"] if x["station_id"] == sid)
        md.append(f"| {now()} | {st['failure_probability'] * 100:.1f}% | {st['risk_band']} | {st['window_end'][11:19]} |")
        print(md[-1], flush=True)
        if st["risk_band"] == "NORMAL" and st["failure_probability"] < 0.2:
            break
        time.sleep(15)

head = (f"# End-to-end fault injection through the app\n\nRun {datetime.now(timezone.utc).isoformat()} against `{APP}`.\n"
        f"Station **{sid}**, injected at **{injected_at}**, first HIGH seen in the app at **{first_high}** (UTC).\n"
        f"Every line below is a real API call to the deployed Databricks App.\n\n")
open(a.out, "w").write(head + "\n".join(md) + "\n")
print(json.dumps({"station_id": sid, "injected_at": injected_at, "first_high": first_high,
                  "work_order": wo and wo["work_order_id"]}))
