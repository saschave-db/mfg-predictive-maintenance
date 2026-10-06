"""Run the Genie benchmark set and write a text report (question, Genie SQL, result, reference result, verdict).

Each question is asked in a fresh conversation. The reference SQL runs right after Genie's answer,
so live tables are compared at nearly the same moment.

Usage: python tools/genie_benchmark.py --space-id ID --out evidence/07_genie/benchmark.md
"""
import argparse
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "src")
from databricks.sdk import WorkspaceClient  # noqa: E402
from genie import space_config as cfg  # noqa: E402


def norm(rows):
    out = []
    for r in rows or []:
        vals = []
        for v in r:
            try:
                vals.append(round(float(v), 2))
            except (TypeError, ValueError):
                vals.append(None if v is None else str(v))
        out.append(tuple(vals))
    return out


def values_match(genie_rows, ref_rows):
    """Same row count, and every reference row's values appear in some Genie row (Genie may add or reorder columns)."""
    g, r = [set(x) for x in norm(genie_rows)], norm(ref_rows)
    return len(g) == len(r) and all(any(set(rr) <= gs for gs in g) for rr in r)


def run_sql(w, wh, sql):
    st = w.statement_execution.execute_statement(statement=sql, warehouse_id=wh, wait_timeout="50s")
    return [c.name for c in st.manifest.schema.columns], (st.result.data_array or []) if st.result else []


def table(cols, rows, limit=10):
    if not cols:
        return "_no rows_"
    s = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows[:limit]:
        s += "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n"
    return s + (f"\n... {len(rows) - limit} more rows\n" if len(rows) > limit else "")


ap = argparse.ArgumentParser()
ap.add_argument("--space-id", required=True)
ap.add_argument("--catalog", default="serverless_stable_am1uc2_catalog")
ap.add_argument("--warehouse-id", default="fb9bc265e9f4578a")
ap.add_argument("--profile", default="fevm-serverless-stable-am1uc2")
ap.add_argument("--out", required=True)
a = ap.parse_args()
w = WorkspaceClient(profile=a.profile)
results, md = [], []
for q, ref_sql in cfg.benchmarks(a.catalog) + [(q, None) for q in cfg.SAMPLE_QUESTIONS]:
    t0 = time.time()
    msg = w.genie.start_conversation_and_wait(a.space_id, q)
    secs = time.time() - t0
    text, sql, cols, rows = None, None, [], []
    for att in msg.attachments or []:
        if att.text and att.text.content:
            text = att.text.content
        if att.query:
            sql, text = att.query.query, text or att.query.description
            res = w.genie.get_message_attachment_query_result(a.space_id, msg.conversation_id, msg.message_id,
                                                              att.attachment_id).statement_response
            if res and res.manifest and res.result:
                cols, rows = [c.name for c in res.manifest.schema.columns], res.result.data_array or []
    verdict = "SAMPLE"
    ref_cols, ref_rows = [], []
    if ref_sql:
        # Live tables move between Genie's answer and now: re-run Genie's SQL and the reference back to back.
        if sql:
            cols, rows = run_sql(w, a.warehouse_id, sql)
        ref_cols, ref_rows = run_sql(w, a.warehouse_id, ref_sql)
        verdict = "PASS" if sql and values_match(rows, ref_rows) else "FAIL"
    results.append((q, verdict, round(secs, 1)))
    print(f"{verdict:6s} {secs:5.1f}s  {q}", flush=True)
    md.append(f"### {verdict}: {q}\n\nGenie answered in {secs:.1f} s (conversation `{msg.conversation_id}`).\n\n"
              + (f"Genie text: {text}\n\n" if text else "")
              + (f"Genie SQL:\n```sql\n{sql}\n```\n\nGenie SQL result (re-executed next to the reference):\n\n{table(cols, rows)}\n" if sql else "_no SQL generated_\n\n")
              + (f"Reference SQL:\n```sql\n{ref_sql}\n```\n\nReference result:\n\n{table(ref_cols, ref_rows)}\n" if ref_sql else ""))

graded = [r for r in results if r[1] != "SAMPLE"]
passed = sum(r[1] == "PASS" for r in graded)
head = (f"# Genie benchmark results\n\nSpace `{a.space_id}` · run {datetime.now(timezone.utc).isoformat()} · "
        f"**{passed}/{len(graded)} benchmark questions matched the reference SQL result** "
        f"(Genie's SQL and the reference SQL are executed back to back on the same warehouse; values compared after rounding; Genie may add columns).\n\n| verdict | seconds | question |\n|---|---|---|\n"
        + "".join(f"| {v} | {s} | {q} |\n" for q, v, s in results) + "\n")
open(a.out, "w").write(head + "\n".join(md))
print(f"{passed}/{len(graded)} passed -> {a.out}")
