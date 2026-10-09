# Build progress

Workspace profile `fevm-serverless-stable-am1uc2`. Bundle target `demo`. All data synthetic.

## Status (2026-10-06): build complete

| # | Step | State | Evidence |
|---|---|---|---|
| 0 | UC schemas, Zerobus target table, reference data, SP grants | Done | `evidence/01_setup/` |
| 1 | Zerobus simulator (serverless job, 96 stations at 1 Hz, 3 streams) | Done | `evidence/02_zerobus_simulator/` |
| 2 | 24 h labeled history backfill | Done | `evidence/03_backfill/` |
| 3 | Model training, UC registry, `@champion` = v2 | Done | `evidence/04_training/` |
| 4 | SDP continuous pipeline (merged windowing + scoring) | Running | `evidence/06_live_pipeline/`, `evidence/09_deployed_resources/sdp_pipeline.json` |
| 5 | Lakebase OLTP tables + Lakehouse Sync to UC | Done | `evidence/06_live_pipeline/` (CDC history of commands) |
| 6 | Continuous synced table `pdm_live.station_risk_scores` | Online | `evidence/09_deployed_resources/lakebase_synced_table.json` |
| 7 | Governance + metric views + tags | Done | `evidence/05_governance_semantic/` |
| 8 | Model Serving `pdm-station-risk` (v2, scale to zero) | Ready | `evidence/08_app/whatif_warm.md` |
| 9 | Genie agent, benchmark 10/10 | Done | `evidence/07_genie/` |
| 10 | App `pdm-plant-health-live` + grants | Running | `evidence/08_app/` |
| 11 | End-to-end fault injection | Done | `evidence/08_app/e2e_fault_injection.md` |
| 12 | Evidence notebooks E00 to E09 (job `pdm_evidence_notebooks`, run 994447175034582) | Done, all SUCCESS | `evidence/10_evidence_notebooks/` |
| 13 | Requirement matrix, source snapshot (SHA256SUMS), non-owner governance proof | Done | README, `evidence/source_snapshot/`, `evidence/08_app/governance_as_app_sp.json` |
| 14 | Industry context (2026-10-09): OEM programs, JIS terms, process steps, `pdm_ops.oem_delivery_exposure`; Genie 12/12 | Done | `evidence/11_industry_context/`, `evidence/07_genie/benchmark.md` |

Decision 2026-10-06: accept about 60 s sensor-to-screen latency and document it (see README, Known limitations).

## Paused (2026-10-07, after evidence hardening)

Everything that costs compute is stopped: simulator run `599986915233103` cancelled, both pipelines IDLE, app stopped,
Lakebase endpoint disabled. The serving endpoint scales to zero on its own. AI Gateway usage tracking stays enabled
(declared in `resources/serving.yml`).

Resume in this order (profile `fevm-serverless-stable-am1uc2`):
1. `databricks postgres update-endpoint projects/pdm-demo/branches/production/endpoints/primary spec.disabled --json '{"spec": {"disabled": false}}'`
2. `databricks pipelines start-update 5135c1d5-fce7-4893-898c-d902dc34a0ea` (synced table) and `databricks pipelines start-update b5544be9-b72f-4e83-b029-1a7151fc53c1` (SDP)
3. `databricks jobs run-now --json '{"job_id": 16077621483238, "job_parameters": {"duration_min": "180", "extra_args": ""}}'` (simulator)
4. `databricks apps start pdm-plant-health-live`
5. Optional: re-run job `pdm_evidence_notebooks` to regenerate the evidence live.

## Possible next steps

- Lower latency: shorter watermark or tumbling 30 s windows (needs a retrain and a full refresh).
- On-behalf-of-user auth for Genie in the app, so row filters apply per viewer.
- Optional: Knowledge Assistant over synthetic maintenance manuals + Supervisor agent.
