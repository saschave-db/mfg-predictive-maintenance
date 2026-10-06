"""Shared helpers for the evidence notebooks."""
import json
import ssl

from databricks.sdk import WorkspaceClient

CATALOG = "serverless_stable_am1uc2_catalog"
PIPELINE_ID = "b5544be9-b72f-4e83-b029-1a7151fc53c1"
LAKEBASE_ENDPOINT = "projects/pdm-demo/branches/production/endpoints/primary"
GENIE_SPACE_ID = "01f1c10d662111078cd7326dff1774c6"
SERVING_ENDPOINT = "pdm-station-risk"
APP_NAME = "pdm-plant-health-live"
ZEROBUS_SP = "240a5501-f956-4282-a2a7-ccc7614683a7"
WAREHOUSE_ID = "fb9bc265e9f4578a"

w = WorkspaceClient()


def show(obj):
    """Pretty-print an SDK object or dict as JSON (text evidence)."""
    d = obj.as_dict() if hasattr(obj, "as_dict") else obj
    print(json.dumps(d, indent=2, default=str))


def pg():
    """Connection to Lakebase as the notebook user (short-lived OAuth token, pure-Python driver)."""
    import pg8000.native
    ep = w.postgres.get_endpoint(name=LAKEBASE_ENDPOINT)
    token = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
    return pg8000.native.Connection(user=w.current_user.me().user_name, host=ep.status.hosts.host,
                                    database="databricks_postgres", password=token,
                                    ssl_context=ssl.create_default_context())


def pg_table(conn, sql, params=None, limit=50):
    """Run SQL on Lakebase and print a markdown table."""
    rows = conn.run(sql, **(params or {}))
    cols = [c["name"] for c in conn.columns] if conn.columns else []
    print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
    for r in rows[:limit]:
        print("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")
    return rows
