# Executed notebook: E03_ml_model

Exported from Databricks job run `994447175034582` (task `E03_ml_model`, task run `864594253859726`).

Result: **SUCCESS** · start 2026-10-07T23:42:04.825000+00:00 · end 2026-10-07T23:43:21.726000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/994447175034582


# E03 · ML: failure-probability model (MLflow, UC registry, in-stream + Model Serving)

**What was built.** Notebook `02_train_model` trains a HistGradientBoosting classifier on 24 h of simulated history
(828k windows, 5.4% positive). Label: the station fails, or would fail without intervention, within 300 s.
Features come from `pdm.features.window_features`, the same function the pipeline runs in-stream. The model is
registered in Unity Catalog as `pdm_ml.station_failure_model` with alias `@champion`, scored inside the SDP pipeline
(`mlflow.pyfunc.spark_udf`), and served on endpoint `pdm-station-risk` for what-if requests.

**What this notebook proves.**
1. Model versions, alias, and the logged evaluation metrics in MLflow.
2. **Consistency:** live windows scored by the pipeline produce the same probability when re-scored here with the
   registered model and through the Model Serving endpoint (no training/serving skew).

```python
%pip install -q "databricks-sdk>=0.81" pg8000
%restart_python
```

Output:

```text
[43mNote: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.[0m
```

```python
from _helpers import *  # noqa: F401,F403
import sys, os, time, json
sys.path.append(os.path.abspath("../.."))
import mlflow
from mlflow import MlflowClient
from pdm.features import FEATURE_COLUMNS

mlflow.set_registry_uri("databricks-uc")
MODEL = f"{CATALOG}.pdm_ml.station_failure_model"
client = MlflowClient()
```

## 1 · Registered model, versions, alias

```python
rm = client.get_registered_model(MODEL)
print("model:", rm.name, "| aliases:", rm.aliases)
print("description:", rm.description)
for v in client.search_model_versions(f"name = '{MODEL}'"):
    print(f"version {v.version}: status={v.status}, run_id={v.run_id}, created={v.creation_timestamp}")
```

Output:

```text
model: serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model | aliases: {'champion': '2'}
description: P(station needs maintenance within 300 s) from 2-minute sliding-window sensor features. HistGradientBoosting; trained on synthetic simulated history. Scored in-stream by SDP and served on pdm-station-risk.
version 2: status=READY, run_id=7ba8c4bb178c4eafb6082654dc729699, created=1791239996873
version 1: status=READY, run_id=5890b84d65854f8298fc8ddfb27a6901, created=1791238641820
```

## 2 · Evaluation metrics logged with the `@champion` version

```python
champ = client.get_model_version_by_alias(MODEL, "champion")
run = mlflow.get_run(champ.run_id)
print("champion version:", champ.version, "| run:", run.info.run_name, run.info.run_id)
for k in sorted(run.data.metrics):
    print(f"  {k:32s} {run.data.metrics[k]:.4f}")
print("params:", {k: run.data.params[k] for k in sorted(run.data.params)})
```

Output:

```text
champion version: 2 | run: hgb_station_failure 7ba8c4bb178c4eafb6082654dc729699
  base_rate                        0.0548
  failures_detected_pct            100.0000
  failures_in_test                 271.0000
  median_lead_time_s               243.8513
  precision_at_0.4                 0.8611
  precision_at_0.7                 0.9477
  recall_at_0.4                    0.8567
  recall_at_0.7                    0.8026
  recall_at_10pct_alert_rate       0.9172
  test_pr_auc                      0.9096
  test_roc_auc                     0.9684
params: {'horizon_s': '300', 'l2_regularization': '1.0', 'learning_rate': '0.08', 'max_iter': '300', 'max_leaf_nodes': '31', 'n_features': '28', 'random_state': '42', 'sklearn': '1.7.2'}
```

## 3 · Consistency: pipeline score vs registered model vs Model Serving
Take the latest scored window for 12 stations (highest and lowest risk), re-score the same feature vectors.

```python
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
```

Output:

| station_id | window_end | risk_band | failure_probability | p_registry | p_serving | max_abs_diff |
|---|---|---|---|---|---|---|
| PLT-N-D07 | 2026-10-07T23:41:50.000Z | ELEVATED | 0.5223 | 0.5223 | 0.5223 | 0.0 |
| PLT-S-C02 | 2026-10-07T23:41:50.000Z | NORMAL | 0.2678 | 0.2678 | 0.2678 | 0.0 |
| PLT-E-C06 | 2026-10-07T23:41:50.000Z | NORMAL | 0.2588 | 0.2588 | 0.2588 | 0.0 |
| PLT-E-C05 | 2026-10-07T23:41:50.000Z | NORMAL | 0.1583 | 0.1583 | 0.1583 | 0.0 |
| PLT-N-A08 | 2026-10-07T23:41:50.000Z | NORMAL | 0.1075 | 0.1075 | 0.1075 | 0.0 |
| PLT-S-C04 | 2026-10-07T23:41:50.000Z | NORMAL | 0.1052 | 0.1052 | 0.1052 | 0.0 |
| PLT-S-B06 | 2026-10-07T23:41:50.000Z | NORMAL | 0.0008 | 0.0008 | 0.0008 | 0.0 |
| PLT-N-D05 | 2026-10-07T23:41:50.000Z | NORMAL | 0.0016 | 0.0016 | 0.0016 | 0.0 |
| PLT-E-D05 | 2026-10-07T23:41:50.000Z | NORMAL | 0.0022 | 0.0022 | 0.0022 | 0.0 |
| PLT-N-B08 | 2026-10-07T23:41:50.000Z | NORMAL | 0.0026 | 0.0026 | 0.0026 | 0.0 |
| PLT-N-C05 | 2026-10-07T23:41:50.000Z | NORMAL | 0.003 | 0.003 | 0.003 | 0.0 |
| PLT-S-D01 | 2026-10-07T23:41:50.000Z | NORMAL | 0.0033 | 0.0033 | 0.0033 | 0.0 |

Output:

```text
Model Serving round trip for 12 rows: 620 ms
max |pipeline - registry| = 5e-05 | max |pipeline - serving| = 5e-05 (pipeline rounds to 4 decimals)
```

## 4 · Raw Model Serving call (HTTP request and response as sent and received)

```python
one = {k: float(v) for k, v in X.iloc[0].items()}
body = {"dataframe_records": [one]}
t0 = time.perf_counter()
raw = w.api_client.do("POST", f"/serving-endpoints/{SERVING_ENDPOINT}/invocations", body=body)
ms = (time.perf_counter() - t0) * 1000
print(f"POST {w.config.host}/serving-endpoints/{SERVING_ENDPOINT}/invocations  ({ms:.0f} ms)")
print("request body:", json.dumps(body)[:1200])
print("response body:", json.dumps(raw))
print(f"station {live.iloc[0].station_id}: pipeline score {live.iloc[0].failure_probability} vs serving {raw['predictions'][0]:.4f}")
```

Output:

```text
POST https://fevm-serverless-stable-am1uc2.cloud.databricks.com/serving-endpoints/pdm-station-risk/invocations  (83 ms)
request body: {"dataframe_records": [{"vibration_rms_mean": 1.0953020833333331, "vibration_rms_std": 0.12489091835365745, "vibration_rms_max": 1.3737499999999998, "vibration_rms_min": 0.75625, "bearing_temp_c_mean": 1.034068611111111, "bearing_temp_c_std": 0.02713430176587955, "bearing_temp_c_max": 1.0997999999999999, "bearing_temp_c_min": 0.96625, "motor_current_a_mean": 1.028954861111111, "motor_current_a_std": 0.03961007250458002, "motor_current_a_max": 1.1327666666666665, "motor_current_a_min": 0.9198666666666667, "spindle_rpm_mean": 1.028078111111111, "spindle_rpm_std": 0.010073533921344989, "spindle_rpm_max": 1.0525, "spindle_rpm_min": 0.9993299999999999, "hydraulic_pressure_bar_mean": 1.0395930555555555, "hydraulic_pressure_bar_std": 0.02112380467873149, "hydraulic_pressure_bar_max": 1.0825, "hydraulic_pressure_bar_min": 0.9791666666666666, "acoustic_db_mean": 1.0080517857142857, "acoustic_db_std": 0.015887128788115438, "acoustic_db_max": 1.0536857142857141, "acoustic_db_min": 0.9748857142857144, "cycle_time_s_mean": 0.9662758333333332, "cycle_time_s_std": 0.031527297751336086, "cycle_time_s_max": 1.0558999999999998, "cycle_time_s_min": 0.8925000000000001}]}
response body: {"predictions": [0.5222891376691063]}
station PLT-N-D07: pipeline score 0.5223 vs serving 0.5223
```

## 5 · AI Gateway on the serving endpoint
The endpoint has AI Gateway usage tracking enabled (declared in `resources/serving.yml`). Every call to
`/serving-endpoints/pdm-station-risk/invocations`, from the app (as its service principal) or from notebooks, is
recorded in `system.serving.endpoint_usage`. System tables can lag behind live calls by some minutes.

```python
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
```

Output:

```text
gateway URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/serving-endpoints/pdm-station-risk/invocations
{
  "endpoint": "pdm-station-risk",
  "ai_gateway": {
    "usage_tracking_config": {
      "enabled": true
    }
  }
}
```

Output:

| requester | status_code | requests | first_request | last_request |
|---|---|---|---|---|
| 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 200 | 3 | 2026-10-07T23:23:44.646Z | 2026-10-07T23:23:45.724Z |

Output:

| request_time | requester | status_code | client_request_id | entity_name | entity_version |
|---|---|---|---|---|---|
| 2026-10-07T23:23:45.724Z | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 200 |  | serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model | 2 |
| 2026-10-07T23:23:45.201Z | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 200 |  | serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model | 2 |
| 2026-10-07T23:23:44.646Z | 2a9b01a6-1050-4c7d-b389-45351bf8e97b | 200 |  | serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model | 2 |
