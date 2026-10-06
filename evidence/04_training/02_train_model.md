# Executed notebook: 02_train_model

Exported from Databricks job run `712648366587487` (task `train`, task run `827496514308622`).

Result: **SUCCESS** · start 2026-10-05T22:38:05.412000+00:00 · end 2026-10-05T22:40:07.028000+00:00

Run URL: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/?o=7474651880045550#job/269340780177784/run/712648366587487


# 02 · Train the station failure model
* Features: `pdm.features.window_features`, the **same function** the SDP pipeline runs in-stream (no training/serving skew).
* Label: the station fails (or would fail without intervention) within the next 300 s after the window end.
* Time-based split (no leakage across time), PR-AUC plus **lead time before failure** as the business metric.
* Registered in Unity Catalog as `pdm_ml.station_failure_model@champion`; the pyfunc returns probabilities.

```python
dbutils.widgets.text("catalog", "serverless_stable_am1uc2_catalog")
CATALOG = dbutils.widgets.get("catalog")

import os, sys
sys.path.append(os.path.abspath(".."))
import mlflow
import numpy as np
import pandas as pd
import sklearn
from mlflow.models import infer_signature
from pyspark.sql import functions as F
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score

from pdm.config import HORIZON_S, MODEL_ALIAS, MODEL_NAME
from pdm.features import FEATURE_COLUMNS, normalize, window_features

MODEL_FQN = f"{CATALOG}.pdm_ml.{MODEL_NAME}"
print("sklearn", sklearn.__version__, "| mlflow", mlflow.__version__)
```

Output:

```text
sklearn 1.7.2 | mlflow 3.12.0
```

## Build the training set with the shared feature definition

```python
hist = spark.table(f"{CATALOG}.pdm_ml.history_readings")
sm = spark.table(f"{CATALOG}.pdm_raw.station_master")
feats = window_features(
    normalize(hist, sm),
    extra_aggs=[F.max_by("ttf_s", "ts").alias("ttf_at_end"), F.max_by("true_failure_mode", "ts").alias("true_failure_mode")],
).withColumn("label", F.coalesce((F.col("ttf_at_end") <= HORIZON_S).cast("int"), F.lit(0)))
# Drop partial windows at the edges of the history.
feats = feats.filter("n_readings >= 110")
feats.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.pdm_ml.training_features")
display(spark.sql(f"""
SELECT count(*) AS windows, sum(label) AS positive_windows, round(avg(label) * 100, 2) AS positive_pct,
       min(window_end) AS first_window, max(window_end) AS last_window
FROM {CATALOG}.pdm_ml.training_features"""))
```

Output:

| windows | positive_windows | positive_pct | first_window | last_window |
|---|---|---|---|---|
| 828576 | 45084 | 5.44 | 2026-10-04T21:01:50.000Z | 2026-10-05T21:00:10.000Z |

```python
tf = spark.table(f"{CATALOG}.pdm_ml.training_features")
cutoff = tf.selectExpr("percentile_approx(unix_timestamp(window_end), 0.75) AS c").first().c
train_sdf = tf.filter(F.unix_timestamp("window_end") < cutoff)
test_sdf = tf.filter(F.unix_timestamp("window_end") >= cutoff + 600)  # 10-minute gap between train and test
# Down-sample easy negatives in train; keep the full test distribution.
train_pdf = train_sdf.filter("label = 1 OR rand(42) < 0.35").select(*FEATURE_COLUMNS, "label").toPandas()
test_pdf = test_sdf.select("station_id", "window_end", "ttf_at_end", "true_failure_mode", *FEATURE_COLUMNS, "label").toPandas()
print(f"train rows {len(train_pdf):,} (pos {train_pdf.label.mean():.1%}) | test rows {len(test_pdf):,} (pos {test_pdf.label.mean():.1%})")
```

## Train and evaluate

```python
class StationRiskModel(mlflow.pyfunc.PythonModel):
    """Returns P(failure within horizon) per row of window features."""

    def __init__(self, clf, feature_columns):
        self.clf, self.feature_columns = clf, feature_columns

    def predict(self, context, model_input, params=None):
        return self.clf.predict_proba(model_input[self.feature_columns].astype("float64"))[:, 1]


mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/pdm_station_failure_model")
params = dict(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=1.0, random_state=42)

with mlflow.start_run(run_name="hgb_station_failure") as run:
    clf = HistGradientBoostingClassifier(**params).fit(train_pdf[FEATURE_COLUMNS], train_pdf.label)
    p = clf.predict_proba(test_pdf[FEATURE_COLUMNS])[:, 1]
    test_pdf["p"] = p
    alert_thr = float(np.quantile(p, 0.90))  # top-10% alert budget
    metrics = {
        "test_pr_auc": average_precision_score(test_pdf.label, p),
        "test_roc_auc": roc_auc_score(test_pdf.label, p),
        "precision_at_0.7": precision_score(test_pdf.label, p >= 0.7),
        "recall_at_0.7": recall_score(test_pdf.label, p >= 0.7),
        "precision_at_0.4": precision_score(test_pdf.label, p >= 0.4),
        "recall_at_0.4": recall_score(test_pdf.label, p >= 0.4),
        "recall_at_10pct_alert_rate": recall_score(test_pdf.label, p >= alert_thr),
        "base_rate": float(test_pdf.label.mean()),
    }

    # Lead time: for each failure in the test window, how long before failure did risk first reach >= 0.7?
    leads = []
    for (sid, mode), g in test_pdf[test_pdf.ttf_at_end.notna() & (test_pdf.ttf_at_end > 0)].groupby(["station_id", "true_failure_mode"]):
        g = g.sort_values("window_end")
        episode = (g.ttf_at_end.diff() > 0).cumsum()  # ttf jumps up -> new episode
        for _, e in g.groupby(episode):
            if e.ttf_at_end.min() > 30:
                continue  # episode not ending in the test window
            hit = e[e.p >= 0.7]
            leads.append(dict(station_id=sid, failure_mode=mode,
                              lead_time_s=float(hit.ttf_at_end.max()) if len(hit) else 0.0))
    leads = pd.DataFrame(leads)
    metrics["failures_in_test"] = len(leads)
    metrics["failures_detected_pct"] = float((leads.lead_time_s > 0).mean() * 100)
    metrics["median_lead_time_s"] = float(leads.lead_time_s.median())

    mlflow.log_params({**params, "horizon_s": HORIZON_S, "n_features": len(FEATURE_COLUMNS), "sklearn": sklearn.__version__})
    mlflow.log_metrics(metrics)
    sample = test_pdf[FEATURE_COLUMNS].head(20)
    model = StationRiskModel(clf, FEATURE_COLUMNS)
    info = mlflow.pyfunc.log_model(
        name="model", python_model=model,
        signature=infer_signature(sample, model.predict(None, sample)),
        input_example=sample.head(3),
        pip_requirements=[f"scikit-learn=={sklearn.__version__}", f"pandas=={pd.__version__}", f"numpy=={np.__version__}"],
        registered_model_name=MODEL_FQN,
    )

for k, v in metrics.items():
    print(f"{k:32s} {v:.4f}" if isinstance(v, float) else f"{k:32s} {v}")
print("\nmlflow run:", run.info.run_id)
```

Output:

```text
🔗 View Logged Model at: https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/experiments/2742082353844011/models/m-e1c8d9b464594dbea272540bc2f34d46?o=7474651880045550
2026/10/05 22:39:53 INFO mlflow.pyfunc: Validating input example against model signature
Registered model 'serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model' already exists. Creating a new version of this model...
```

Output:

```text
🔗 Created version '2' of model 'serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model': https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/models/serverless_stable_am1uc2_catalog/pdm_ml/station_failure_model/version/2?o=7474651880045550
```

Output:

```text
test_pr_auc                      0.9096
test_roc_auc                     0.9684
precision_at_0.7                 0.9477
recall_at_0.7                    0.8026
precision_at_0.4                 0.8611
recall_at_0.4                    0.8567
recall_at_10pct_alert_rate       0.9172
base_rate                        0.0548
failures_in_test                 271
failures_detected_pct            100.0000
median_lead_time_s               243.8513

mlflow run: 7ba8c4bb178c4eafb6082654dc729699
```

```python
display(leads.groupby("failure_mode").agg(failures=("lead_time_s", "size"),
                                          detected_pct=("lead_time_s", lambda s: round((s > 0).mean() * 100, 1)),
                                          median_lead_s=("lead_time_s", "median")).reset_index())
```

Output:

| failure_mode | failures | detected_pct | median_lead_s |
|---|---|---|---|
| bearing_wear | 82 | 100.0 | 189.88280391693115 |
| overheating | 132 | 100.0 | 251.86607718467712 |
| seal_leak | 57 | 100.0 | 268.2173888683319 |

## Register `@champion` and smoke-test the registered model

```python
from mlflow import MlflowClient

client = MlflowClient()
version = info.registered_model_version
client.set_registered_model_alias(MODEL_FQN, MODEL_ALIAS, version)
client.update_registered_model(MODEL_FQN, description=(
    "P(station needs maintenance within 300 s) from 2-minute sliding-window sensor features. "
    "HistGradientBoosting; trained on synthetic simulated history. Scored in-stream by SDP and served on pdm-station-risk."))
print(f"{MODEL_FQN} version {version} -> @{MODEL_ALIAS}")

loaded = mlflow.pyfunc.load_model(f"models:/{MODEL_FQN}@{MODEL_ALIAS}")
demo = test_pdf.sort_values("p").iloc[np.linspace(0, len(test_pdf) - 1, 8).astype(int)]
demo = demo.assign(p_registered=loaded.predict(demo[FEATURE_COLUMNS]))
display(demo[["station_id", "window_end", "true_failure_mode", "ttf_at_end", "label", "p", "p_registered"]])
```

Output:

```text
serverless_stable_am1uc2_catalog.pdm_ml.station_failure_model version 2 -> @champion
```

Output:

| station_id | window_end | true_failure_mode | ttf_at_end | label | p | p_registered |
|---|---|---|---|---|---|---|
| PLT-S-B02 | 2026-10-05T18:51:30.000Z |  |  | 0 | 0.0004141884606624675 | 0.0004141884606624675 |
| PLT-E-A06 | 2026-10-05T20:46:30.000Z |  |  | 0 | 0.004401084589781034 | 0.004401084589781034 |
| PLT-S-D02 | 2026-10-05T19:44:10.000Z |  |  | 0 | 0.006544657445518679 | 0.006544657445518679 |
| PLT-N-C07 | 2026-10-05T18:44:00.000Z |  |  | 0 | 0.00884279705470177 | 0.00884279705470177 |
| PLT-N-D07 | 2026-10-05T19:43:10.000Z |  |  | 0 | 0.011901574099194446 | 0.011901574099194446 |
| PLT-E-D05 | 2026-10-05T15:32:40.000Z |  |  | 0 | 0.017299755806529035 | 0.017299755806529035 |
| PLT-S-D06 | 2026-10-05T19:43:00.000Z |  |  | 0 | 0.03548862045870944 | 0.03548862045870944 |
| PLT-E-A01 | 2026-10-05T19:14:20.000Z | seal_leak | 36.098942279815674 | 1 | 0.9999771657875027 | 0.9999771657875027 |
