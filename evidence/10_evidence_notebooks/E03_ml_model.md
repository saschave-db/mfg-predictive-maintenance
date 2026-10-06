# Executed notebook: E03_ml_model

Exported from Databricks job run `980301348000608` (task `E03_ml_model`, task run `678790405288660`).

Result: **SUCCESS** · start 2026-10-06T17:43:19.820000+00:00 · end 2026-10-06T17:43:49.971000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/755461157363253/run/980301348000608


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
import sys, os, time
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
| PLT-N-C04 | 2026-10-06T17:42:40.000Z | HIGH | 0.9989 | 0.9989 | 0.9989 | 0.0 |
| PLT-E-A07 | 2026-10-06T17:42:40.000Z | HIGH | 0.9969 | 0.9969 | 0.9969 | 0.0 |
| PLT-E-B02 | 2026-10-06T17:42:40.000Z | HIGH | 0.953 | 0.953 | 0.953 | 0.0 |
| PLT-S-C02 | 2026-10-06T17:42:40.000Z | HIGH | 0.7762 | 0.7762 | 0.7762 | 0.0 |
| PLT-S-A06 | 2026-10-06T17:42:40.000Z | ELEVATED | 0.5645 | 0.5645 | 0.5645 | 0.0 |
| PLT-S-B05 | 2026-10-06T17:42:40.000Z | NORMAL | 0.3964 | 0.3964 | 0.3964 | 0.0 |
| PLT-S-D01 | 2026-10-06T17:42:40.000Z | NORMAL | 0.0009 | 0.0009 | 0.0009 | 0.0 |
| PLT-E-B05 | 2026-10-06T17:42:40.000Z | NORMAL | 0.001 | 0.001 | 0.001 | 0.0 |
| PLT-N-B08 | 2026-10-06T17:42:40.000Z | NORMAL | 0.0011 | 0.0011 | 0.0011 | 0.0 |
| PLT-N-C05 | 2026-10-06T17:42:40.000Z | NORMAL | 0.0018 | 0.0018 | 0.0018 | 0.0 |
| PLT-S-D06 | 2026-10-06T17:42:40.000Z | NORMAL | 0.0019 | 0.0019 | 0.0019 | 0.0 |
| PLT-S-B06 | 2026-10-06T17:42:40.000Z | NORMAL | 0.002 | 0.002 | 0.002 | 0.0 |

Output:

```text
Model Serving round trip for 12 rows: 442 ms
max |pipeline - registry| = 5e-05 | max |pipeline - serving| = 5e-05 (pipeline rounds to 4 decimals)
```
