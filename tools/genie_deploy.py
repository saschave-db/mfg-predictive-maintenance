"""Create or update the Genie agent from src/genie/space_config.py.

Usage: python tools/genie_deploy.py [--space-id ID] [--profile P]
"""
import argparse
import json
import sys

sys.path.insert(0, "src")
from databricks.sdk import WorkspaceClient  # noqa: E402
from genie import space_config as cfg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--space-id", default="")
ap.add_argument("--catalog", default="serverless_stable_am1uc2_catalog")
ap.add_argument("--warehouse-id", default="fb9bc265e9f4578a")
ap.add_argument("--profile", default="fevm-serverless-stable-am1uc2")
a = ap.parse_args()
w = WorkspaceClient(profile=a.profile)
body = {"warehouse_id": a.warehouse_id, "title": cfg.TITLE, "description": cfg.DESCRIPTION,
        "serialized_space": cfg.build_serialized_space(a.catalog)}
if a.space_id:
    r = w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{a.space_id}", body=body)
else:
    r = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
print(json.dumps({k: r.get(k) for k in ("space_id", "title", "warehouse_id")}, indent=2))
