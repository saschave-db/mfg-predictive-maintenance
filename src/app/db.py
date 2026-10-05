"""Lakebase access for the app: psycopg pool with OAuth tokens minted for the app service principal."""
import os
import time
import threading

import psycopg
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
ENDPOINT = os.environ["LAKEBASE_ENDPOINT"]  # projects/<p>/branches/<b>/endpoints/<e>
_token = {"value": None, "at": 0.0}
_lock = threading.Lock()


def _password() -> str:
    with _lock:
        if not _token["value"] or time.time() - _token["at"] > 30 * 60:  # tokens live ~1 h
            _token["value"] = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
            _token["at"] = time.time()
        return _token["value"]


class TokenConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", **kwargs):
        kwargs["password"] = _password()
        return super().connect(conninfo, **kwargs)


HOST = os.environ.get("PGHOST") or w.postgres.get_endpoint(name=ENDPOINT).status.hosts.host

pool = ConnectionPool(
    conninfo=(f"host={HOST} dbname={os.environ.get('PGDATABASE', 'databricks_postgres')} "
              f"user={os.environ.get('PGUSER') or w.config.client_id} sslmode=require"),
    connection_class=TokenConnection, min_size=1, max_size=8, max_lifetime=45 * 60,
    kwargs={"autocommit": True}, open=False,
)


def query(sql: str, params=None) -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if not cur.description:
            return []
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
