"""Live plant-gateway simulator: pushes 1 Hz station telemetry into Unity Catalog via Zerobus Ingest.

One Zerobus stream per plant gateway (3 streams). Fault injection comes from:
  * --inject "<offset_s>:<station_id>[:<mode>]" arguments (scripted, for evidence runs)
  * the Lakebase table sim_commands (interactive, from the app), when --lakebase-* args are given
All data is synthetic.
"""
import argparse
import json
import logging
import os
import shlex
import ssl
import sys
import time
from collections import Counter, defaultdict

# Serverless Python tasks have no __file__; the bundle passes --src-path explicitly.
_src = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--src-path=")), None)
sys.path.append(_src or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from databricks.sdk import WorkspaceClient  # noqa: E402
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties  # noqa: E402
from zerobus.sdk.sync import ZerobusSdk  # noqa: E402

from pdm.physics import Fleet, build_station_master  # noqa: E402
from pdm.config import SENSORS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("producer")
logging.getLogger("zerobus").setLevel(logging.WARNING)

FIRMWARE = "gw-fw-3.2.1"


class GatewayStreams:
    """One Zerobus stream per gateway, recreated on failure (at-least-once; silver de-duplicates)."""

    def __init__(self, sdk, client_id, client_secret, table):
        self.sdk, self.cid, self.secret, self.table = sdk, client_id, client_secret, table
        self.opts = StreamConfigurationOptions(record_type=RecordType.JSON)
        self.streams = {}
        self.last_offset = {}

    def _stream(self, gw):
        if gw not in self.streams:
            self.streams[gw] = self.sdk.create_stream(self.cid, self.secret, TableProperties(self.table), self.opts)
            log.info("opened Zerobus stream for %s", gw)
        return self.streams[gw]

    def send(self, gw, records):
        for attempt in range(5):
            try:
                s = self._stream(gw)
                for r in records:
                    self.last_offset[gw] = s.ingest_record_offset(r)
                return
            except Exception as e:  # reconnect with backoff
                log.warning("stream %s error (attempt %d): %s", gw, attempt + 1, e)
                try:
                    self.streams.pop(gw).close()
                except Exception:
                    pass
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"giving up on gateway {gw}")

    def wait_durable(self):
        for gw, off in self.last_offset.items():
            self.streams[gw].wait_for_offset(off)

    def close(self):
        for s in self.streams.values():
            try:
                s.flush()
                s.close()
            except Exception as e:
                log.warning("close error: %s", e)


class LakebaseCommands:
    """Polls pending rows in Lakebase pdm_ops.sim_commands (inject_fault / repair) and marks them applied.

    Uses pg8000 (pure Python). A run using psycopg[binary] next to the Zerobus SDK aborted (SIGABRT); pg8000 avoids native libpq.
    """

    def __init__(self, w: WorkspaceClient, endpoint: str, host: str, database: str, user: str):
        import pg8000.native
        self.pg, self.w, self.endpoint, self.host, self.db, self.user = pg8000.native, w, endpoint, host, database, user
        self.conn, self.conn_at = None, 0

    def _connect(self):
        if self.conn is None or time.time() - self.conn_at > 1800:  # tokens are short-lived
            if self.conn:
                self.conn.close()
            token = self.w.postgres.generate_database_credential(endpoint=self.endpoint).token
            self.conn = self.pg.Connection(user=self.user, host=self.host, database=self.db, password=token,
                                           ssl_context=ssl.create_default_context())
            self.conn_at = time.time()
        return self.conn

    def poll(self):
        try:
            return self._connect().run("""UPDATE pdm_ops.sim_commands SET status = 'applied', applied_at = now()
                                          WHERE status = 'pending'
                                          RETURNING command_id, command, station_id, failure_mode""")
        except Exception as e:
            log.warning("command poll failed: %s", e)
            self.conn = None
            return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--endpoint", required=True, help="Zerobus server endpoint")
    ap.add_argument("--secret-scope", default="pdm-demo")
    ap.add_argument("--duration-min", type=float, default=60)
    ap.add_argument("--inject", action="append", default=[], help="<offset_s>:<station_id>[:<mode>]")
    ap.add_argument("--fast-onset-s", type=float, default=0,
                    help="if >0, injected episodes progress to failure in this many seconds")
    ap.add_argument("--lakebase-endpoint", default="")
    ap.add_argument("--lakebase-host", default="")
    ap.add_argument("--lakebase-database", default="databricks_postgres")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--src-path", default="")
    ap.add_argument("--extra", default="", help="more args as one string (job parameter passthrough)")
    a, _ = ap.parse_known_args()
    if a.extra.strip():
        a, _ = ap.parse_known_args(sys.argv[1:] + shlex.split(a.extra))

    w = WorkspaceClient()
    client_id = w.dbutils.secrets.get(a.secret_scope, "zerobus_client_id")
    client_secret = w.dbutils.secrets.get(a.secret_scope, "zerobus_client_secret")
    table = f"{a.catalog}.pdm_raw.sensor_readings"
    sdk = ZerobusSdk(a.endpoint, w.config.host)
    streams = GatewayStreams(sdk, client_id, client_secret, table)

    stations = build_station_master()
    by_id = {s["station_id"]: s for s in stations}
    t_start = time.time()
    fleet = Fleet(stations, seed=a.seed, t0=t_start)
    injections = []
    for spec in a.inject:
        off, sid, *mode = spec.split(":")
        injections.append((t_start + float(off), sid, mode[0] if mode else None))
    commands = None
    if a.lakebase_endpoint:
        commands = LakebaseCommands(w, a.lakebase_endpoint, a.lakebase_host, a.lakebase_database,
                                    w.current_user.me().user_name)

    log.info("starting: %d stations, table=%s, endpoint=%s, duration=%.1f min, injections=%s",
             len(stations), table, a.endpoint, a.duration_min, a.inject)
    sent, events, tick = 0, Counter(), 0
    last_report, send_lat = t_start, []
    try:
        while time.time() - t_start < a.duration_min * 60:
            t = float(int(time.time()))  # whole-second sample clock
            for (at, sid, mode) in [x for x in injections if x[0] <= t]:
                injections.remove((at, sid, mode))
                i = fleet.index_of(sid)
                ev = fleet.start_episode(i, t, mode, a.fast_onset_s or None)
                log.info("SCRIPTED INJECTION %s -> %s", sid, ev)
            if commands and tick % 2 == 0:
                for cid, cmd, sid, mode in commands.poll():
                    i = fleet.index_of(sid)
                    if i is None:
                        continue
                    ev = (fleet.start_episode(i, t, mode, a.fast_onset_s or None) if cmd == "inject_fault"
                          else fleet.repair(i, t, "preventive_repair"))
                    log.info("COMMAND %s %s %s -> %s", cid, cmd, sid, ev)

            r, evs = fleet.step(t)
            for ev in evs:
                events[ev["event_type"]] += 1
                if ev["event_type"] != "degradation_onset":
                    log.info("EVENT %s", json.dumps(ev))

            ts_us = int(t * 1_000_000)
            batches = defaultdict(list)
            for i, sid in enumerate(fleet.ids):
                s = by_id[sid]
                rec = {"event_id": f"{sid}-{int(t)}", "gateway_id": s["gateway_id"], "plant_id": s["plant_id"],
                       "line_id": s["line_id"], "station_id": sid, "ts": ts_us, "seq": int(t),
                       "firmware": FIRMWARE}
                rec.update({k: float(r[k][i]) for k in SENSORS})
                batches[s["gateway_id"]].append(rec)
            t0 = time.time()
            for gw, recs in batches.items():
                streams.send(gw, recs)
                sent += len(recs)
            if tick % 10 == 0:
                streams.wait_durable()  # durability ACK round-trip
                send_lat.append(time.time() - t0)
            tick += 1

            if time.time() - last_report >= 30:
                degrading = int(sum(1 for m in fleet.mode if m))
                p50 = sorted(send_lat)[len(send_lat) // 2] if send_lat else 0
                log.info("STATS sent=%d rate=%.1f rec/s degrading=%d events=%s ack_roundtrip_p50_ms=%.0f",
                         sent, sent / (time.time() - t_start), degrading, dict(events), p50 * 1000)
                last_report, send_lat = time.time(), []
            time.sleep(max(0.0, t + 1 - time.time()))
    finally:
        streams.close()
        log.info("FINISHED sent=%d events=%s elapsed_s=%.0f", sent, dict(events), time.time() - t_start)


if __name__ == "__main__":
    main()
