# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Train the station failure model
# MAGIC * Features: `pdm.features.window_features`, the **same function** the SDP pipeline runs in-stream (no training/serving skew).
# MAGIC * Label: the station fails (or would fail without intervention) within the next 300 s after the window end.
# MAGIC * Time-based split (no leakage across time), PR-AUC plus **lead time before failure** as the business metric.
# MAGIC * Registered in Unity Catalog as `pdm_ml.station_failure_model@champion`; the pyfunc returns probabilities.

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build the training set with the shared feature definition

# COMMAND ----------

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

# COMMAND ----------

tf = spark.table(f"{CATALOG}.pdm_ml.training_features")
cutoff = tf.selectExpr("percentile_approx(unix_timestamp(window_end), 0.75) AS c").first().c
train_sdf = tf.filter(F.unix_timestamp("window_end") < cutoff)
test_sdf = tf.filter(F.unix_timestamp("window_end") >= cutoff + 600)  # 10-minute gap between train and test
# Down-sample easy negatives in train; keep the full test distribution.
train_pdf = train_sdf.filter("label = 1 OR rand(42) < 0.35").select(*FEATURE_COLUMNS, "label").toPandas()
test_pdf = test_sdf.select("station_id", "window_end", "ttf_at_end", "true_failure_mode", *FEATURE_COLUMNS, "label").toPandas()
print(f"train rows {len(train_pdf):,} (pos {train_pdf.label.mean():.1%}) | test rows {len(test_pdf):,} (pos {test_pdf.label.mean():.1%})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Train and evaluate

# COMMAND ----------

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

# COMMAND ----------

display(leads.groupby("failure_mode").agg(failures=("lead_time_s", "size"),
                                          detected_pct=("lead_time_s", lambda s: round((s > 0).mean() * 100, 1)),
                                          median_lead_s=("lead_time_s", "median")).reset_index())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Register `@champion` and smoke-test the registered model

# COMMAND ----------

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
