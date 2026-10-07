# Databricks notebook source
# MAGIC %md
# MAGIC # E06 · Genie agent on metric views and work orders
# MAGIC
# MAGIC **What was built.** Genie agent "Plant Maintenance Agent", defined as code in `src/genie/space_config.py`:
# MAGIC 3 metric views + `station_health_current` + `work_orders_current`, text instructions (plant naming, risk bands,
# MAGIC compressed time, where to find what), 4 example SQL queries, 4 sample questions and 10 benchmark questions with
# MAGIC reference SQL. Deployed with `tools/genie_deploy.py`.
# MAGIC
# MAGIC **What this notebook proves.** The deployed configuration, and live answers: each benchmark question is asked through
# MAGIC the Genie Conversation API; Genie's generated SQL and the reference SQL are executed back to back and compared.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import sys, os, time, json
sys.path.append(os.path.abspath("../.."))
from genie import space_config as cfg

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Deployed configuration

# COMMAND ----------

sp = w.api_client.do("GET", f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}", query={"include_serialized_space": "true"})
ser = json.loads(sp["serialized_space"])
print("title:", sp["title"], "| warehouse:", sp["warehouse_id"])
print("data sources:", [t["identifier"].split(".", 1)[1] for k in ("tables", "metric_views") for t in ser["data_sources"].get(k, [])])
print("sample questions:", [q["question"][0] for q in ser["config"]["sample_questions"]])
print("example SQL questions:", [q["question"][0] for q in ser["instructions"]["example_question_sqls"]])
print("benchmarks:", len(ser["benchmarks"]["questions"]))
print("\ninstructions:\n" + ser["instructions"]["text_instructions"][0]["content"][0])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Live benchmark: Genie answer vs reference SQL

# COMMAND ----------

def norm(rows):
    out = []
    for r in rows:
        vals = set()
        for v in r:
            try:
                vals.add(round(float(v), 2))
            except (TypeError, ValueError):
                vals.add(None if v is None else str(v))
        out.append(vals)
    return out


results, raw_shown = [], False
for q, ref_sql in cfg.benchmarks(CATALOG):
    t0 = time.time()
    msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q)
    secs = time.time() - t0
    if not raw_shown:  # one complete raw API response, as returned by the Genie Conversation API
        print("RAW Genie message response:\n" + json.dumps(msg.as_dict(), indent=1, default=str)[:4000])
        raw_shown = True
    sql = next((a.query.query for a in (msg.attachments or []) if a.query), None)
    text = next((a.text.content for a in (msg.attachments or []) if a.text and a.text.content), None)
    g_rows = [list(r) for r in spark.sql(sql).collect()] if sql else []
    r_rows = [list(r) for r in spark.sql(ref_sql).collect()]
    ok = bool(sql) and len(g_rows) == len(r_rows) and all(any(rr <= gg for gg in norm(g_rows)) for rr in norm(r_rows))
    results.append((("PASS" if ok else "FAIL"), round(secs, 1), q))
    print(f"\n### {'PASS' if ok else 'FAIL'} ({secs:.1f} s): {q}")
    print("Genie SQL:\n" + (sql or "<none>"))
    print("Genie rows:", g_rows[:5])
    print("Reference rows:", r_rows[:5])
    if text:
        print("Genie text:", text[:400])

# COMMAND ----------

display(spark.createDataFrame(results, "verdict string, seconds double, question string"))
print(f"{sum(r[0] == 'PASS' for r in results)}/{len(results)} benchmark questions match the reference result")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Sample questions (free-form answers)

# COMMAND ----------

for q in cfg.SAMPLE_QUESTIONS:
    msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q)
    sql = next((a.query.query for a in (msg.attachments or []) if a.query), None)
    text = next((a.text.content for a in (msg.attachments or []) if a.text and a.text.content), None)
    print(f"\n### {q}\nGenie text: {text}\nGenie SQL:\n{sql}")
    if sql:
        print("rows:", [list(r) for r in spark.sql(sql).limit(5).collect()])
