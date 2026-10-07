# Databricks notebook source
# MAGIC %md
# MAGIC # E09 · Source integrity: the code that runs is the code in the repo
# MAGIC
# MAGIC `evidence/source_snapshot/` holds a byte-identical copy of the pipeline, shared feature/physics code, simulator and
# MAGIC pipeline config, with `SHA256SUMS` (written by `tools/snapshot_source.py`).
# MAGIC
# MAGIC **What this notebook proves.**
# MAGIC 1. The running SDP pipeline's libraries point to the bundle-deployed files.
# MAGIC 2. The SHA-256 of every **deployed** file equals the committed checksum (and the committed snapshot copy).
# MAGIC 3. The full deployed pipeline source, printed below as text.

# COMMAND ----------

# MAGIC %pip install -q "databricks-sdk>=0.81" pg8000
# MAGIC %restart_python

# COMMAND ----------

from _helpers import *  # noqa: F401,F403
import hashlib, os
ROOT = os.path.abspath("../../..")  # bundle files root in the workspace
print("deployed bundle root:", ROOT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Pipeline libraries as configured on the running pipeline

# COMMAND ----------

p = w.pipelines.get(PIPELINE_ID)
libs = [l.file.path for l in p.spec.libraries]
print("pipeline:", p.name, "| state:", p.state.value, "| continuous:", p.spec.continuous)
for l in libs:
    print("  library:", l, "| under deployed root:", l.startswith(ROOT.replace("/Workspace", "")) or l.startswith(ROOT))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · SHA-256 of deployed files vs committed checksums vs committed snapshot

# COMMAND ----------

sums = {}
for line in open(os.path.join(ROOT, "evidence/source_snapshot/SHA256SUMS")).read().splitlines():
    h, f = line.split("  ", 1)
    sums[f] = h
sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
rows = []
for f, expected in sorted(sums.items()):
    deployed = sha(os.path.join(ROOT, f))
    snapshot = sha(os.path.join(ROOT, "evidence/source_snapshot", f))
    rows.append((f, deployed[:16], expected[:16], snapshot[:16], deployed == expected == snapshot))
display(spark.createDataFrame(rows, "file string, deployed_sha256 string, committed_sha256 string, snapshot_sha256 string, identical boolean"))
print("ALL IDENTICAL" if all(r[-1] for r in rows) else "MISMATCH FOUND")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Full deployed pipeline source

# COMMAND ----------

for f in sorted(k for k in sums if k.startswith("src/pipeline/") or k == "src/pdm/features.py" or k == "resources/pipeline.yml"):
    print(f"{'=' * 100}\n# {f}  sha256={sums[f]}\n{'=' * 100}")
    print(open(os.path.join(ROOT, f)).read())
