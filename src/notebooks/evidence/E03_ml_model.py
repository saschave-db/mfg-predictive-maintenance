# Databricks notebook source
# MAGIC %md
# MAGIC # E03 · ML: failure-probability model (MLflow, UC registry, in-stream + Model Serving)
# MAGIC
# MAGIC **What was built.** Notebook `02_train_model` trains a HistGradientBoosting classifier on 24 h of simulated history
# MAGIC (828k windows, 5.4% positive). Label: the station fails, or would fail without intervention, within 300 s.
# MAGIC Features come from `pdm.features.window_features`, the same function the pipeline runs in-stream. The model is
# MAGIC registered in Unity Catalog as `pdm_ml.station_failure_model` with alias `@champion`, scored inside the SDP pipeline
# MAGIC (`mlflow.pyfunc.spark_udf`), and served on endpoint `pdm-station-risk` for what-if requests.
# MAGIC
# MAGIC **What this notebook proves.**
# MAGIC 1. Model versions, alias, and the logged evaluation metrics in MLflow.
# MAGIC 2. **Consistency:** live windows scored by the pipeline produce the same probability when re-scored here with the
# MAGIC    registered model and through the Model Serving endpoint (no training/serving skew).

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import sys, os, time, json
sys.path.append(os.path.abspath("../.."))
import mlflow
from mlflow import MlflowClient
from pdm.features import FEATURE_COLUMNS

mlflow.set_registry_uri("databricks-uc")
MODEL = f"{CATALOG}.pdm_ml.station_failure_model"
client = MlflowClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Registered model, versions, alias

# COMMAND ----------

rm = client.get_registered_model(MODEL)
print("model:", rm.name, "| aliases:", rm.aliases)
print("description:", rm.description)
for v in client.search_model_versions(f"name = '{MODEL}'"):
    print(f"version {v.version}: status={v.status}, run_id={v.run_id}, created={v.creation_timestamp}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Evaluation metrics logged with the `@champion` version

# COMMAND ----------

champ = client.get_model_version_by_alias(MODEL, "champion")
run = mlflow.get_run(champ.run_id)
print("champion version:", champ.version, "| run:", run.info.run_name, run.info.run_id)
for k in sorted(run.data.metrics):
    print(f"  {k:32s} {run.data.metrics[k]:.4f}")
print("params:", {k: run.data.params[k] for k in sorted(run.data.params)})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Consistency: pipeline score vs registered model vs Model Serving
# MAGIC Take the latest scored window for 12 stations (highest and lowest risk), re-score the same feature vectors.

# COMMAND ----------

live = spark.sql(f"""
(SELECT * FROM {CATALOG}.pdm_core.station_health_current ORDER BY failure_probability DESC LIMIT 6)
UNION ALL (SELECT * FROM {CATALOG}.pdm_core.station_health_current ORDER BY failure_probability ASC LIMIT 6)""").toPandas()
X = live[FEATURE_COLUMNS].astype("float64")
model = mlflow.pyfunc.load_model(f"models:/{MODEL}@champion")
live["p_registry"] = model.predict(X)
t0 = time.perf_counter()
resp = w.serving_endpoints.query(name=SERVING_ENDPOINT, dataframe_records=X.to_dict(orient="records"))
serving_ms = (time.perf_counter() - t0) * 1000
live["p_serving"] = resp.predictions
out = live[["station_id", "window_end", "risk_band", "failure_probability", "p_registry", "p_serving"]].round(4)
out["max_abs_diff"] = (out[["p_registry", "p_serving"]].sub(out.failure_probability, axis=0)).abs().max(axis=1).round(4)
display(out)
print(f"Model Serving round trip for {len(X)} rows: {serving_ms:.0f} ms")
print("max |pipeline - registry| =", float((live.p_registry - live.failure_probability).abs().max()).__round__(5),
      "| max |pipeline - serving| =", float((live.p_serving - live.failure_probability).abs().max()).__round__(5),
      "(pipeline rounds to 4 decimals)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Raw Model Serving call (HTTP request and response as sent and received)

# COMMAND ----------

one = {k: float(v) for k, v in X.iloc[0].items()}
body = {"dataframe_records": [one]}
t0 = time.perf_counter()
raw = w.api_client.do("POST", f"/serving-endpoints/{SERVING_ENDPOINT}/invocations", body=body)
ms = (time.perf_counter() - t0) * 1000
print(f"POST {w.config.host}/serving-endpoints/{SERVING_ENDPOINT}/invocations  ({ms:.0f} ms)")
print("request body:", json.dumps(body)[:1200])
print("response body:", json.dumps(raw))
print(f"station {live.iloc[0].station_id}: pipeline score {live.iloc[0].failure_probability} vs serving {raw['predictions'][0]:.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · AI Gateway on the serving endpoint
# MAGIC The endpoint has AI Gateway usage tracking enabled (declared in `resources/serving.yml`). Every call to
# MAGIC `/serving-endpoints/pdm-station-risk/invocations`, from the app (as its service principal) or from notebooks, is
# MAGIC recorded in `system.serving.endpoint_usage`. System tables can lag behind live calls by some minutes.

# COMMAND ----------

ep = w.serving_endpoints.get(SERVING_ENDPOINT)
print("gateway URL:", f"{w.config.host}/serving-endpoints/{SERVING_ENDPOINT}/invocations")
show({"endpoint": ep.name, "ai_gateway": ep.ai_gateway.as_dict() if ep.ai_gateway else None})
display(spark.sql(f"""
SELECT u.requester, u.status_code, count(*) AS requests, min(u.request_time) AS first_request, max(u.request_time) AS last_request
FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e USING (served_entity_id)
WHERE e.endpoint_name = '{SERVING_ENDPOINT}' GROUP BY ALL ORDER BY last_request DESC"""))
display(spark.sql(f"""
SELECT u.request_time, u.requester, u.status_code, u.client_request_id, e.entity_name, e.entity_version
FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e USING (served_entity_id)
WHERE e.endpoint_name = '{SERVING_ENDPOINT}' ORDER BY u.request_time DESC LIMIT 10"""))
