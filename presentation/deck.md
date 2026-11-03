---
marp: true
theme: volta
title: Volta Industrial. Never stop the OEM line. Live predictive maintenance for EV battery enclosures on Databricks
paginate: true
---

<!-- _class: title -->

# Volta Industrial: never be the supplier that stops the OEM line

**Live predictive maintenance for aluminum EV battery enclosures, on one Databricks platform**

For **Ingrid Solberg**, COO and executive sponsor, and **Linnea Berg**, Lead App Developer, who would own the app

*20 minutes · all companies, people and data are fictional and synthetic*

<!--
0:00 to 0:30. "Thanks, Ingrid. Thanks, Linnea. Twenty minutes. Before I show anything, let me frame why we're here."
-->

---

## Why we're here: the customer, the problem, what you'll see

<div class="meta"><b>0:30 to 2:00</b> · setup</div>

<div class="two">
<div class="card">
<h3>The customer</h3>
Volta Industrial, a Tier-1 supplier. Aluminum battery enclosures for <b>Nordvik Motors, Fjord Electric and Aurora Elbil</b>, shipped just-in-sequence from 12 lines in three plants.
</div>
<div class="card">
<h3>The problem</h3>
Each line holds only <b>45 to 90 minutes</b> of buffer. An unplanned station failure takes <b>112 minutes</b> to fix. So one failure can stop an OEM's assembly line, at about <b>$595,000</b> a time, and a mark on the scorecard that decides the next program.
</div>
</div>

| In the room | What you get from the next 20 minutes |
|---|---|
| **Ingrid Solberg**, COO, funds the decision | What this is worth, how fast, and what the risk is |
| **Linnea Berg**, Lead App Developer, would own the app | How it is built, how data and identity work, and what her team runs |

**What you'll see:** four short demos on one line in Plant East, built for **Bjørn Halvorsen**, its maintenance supervisor.
① **See it coming** · ② **Fix it in a planned break** · ③ **Know the OEM exposure** · ④ **Under the hood**

<!--
Read the room: "Ingrid, is the OEM line stop your biggest worry, or margin?" Then: "Linnea, what matters most when your team inherits an app like this?" Use their words in every landing.
Before the slide ends, inject the overheating fault on PLT-E-A03 in the app, so it is HIGH when demo 1 starts.
-->

---

## The problem, in Volta's own numbers

<div class="meta"><b>2:00 to 4:00</b> · for Ingrid, the business case in one picture</div>

| From the maintenance history (96 stations, 1,096 failures) | Downtime | Parts | Fits a 45 to 90 min JIS buffer? |
|---|---|---|---|
| Repair **after** a failure | **112 min** | **$7,200** | **No.** The OEM line stops for about 44 min: about $595k |
| **Planned** repair | **28 min** | **$870** | **Yes.** The OEM never notices |

- **Today only 20% of repairs are planned.** Four out of five are emergencies.
- The model flagged **271 of 271** failures in a held-out test window, about **4 operating hours** ahead, with **95%** alert precision.

<div class="sowhat"><span class="label">The promise</span> Catch the failure early enough to fix it in a planned break, and an OEM line stop becomes a non-event.</div>

<!--
"Here is your own history." Pause after 112 and after 595,000. "Let me show you what that looks like on Bjørn's line."
Say once: "In the demo, one minute is about one operating hour, so you see a shift in a few minutes."
-->

---

## Demo ① See it coming

<div class="meta"><b>4:00 to 7:00</b> · for both · station PLT-E-A03, frame welder, Aurora Elbil A3 Hatch line, 60-minute buffer</div>

<div class="tell"><span class="label">Tell</span> "This is Bjørn's screen: all 96 stations, live. Watch the frame welder on the Aurora Elbil line."</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com" target="_blank">Plant Health Live app</a></div>

- The welder starts green at about **1%** risk, climbs, then turns **HIGH** (79%, then 99%).
- The screen says **why**: motor current about **10% above normal**. The technician knows where to look.
- *For Linnea:* the header badge shows **data age** and **Lakebase query time**, live. The page polls every 2 s; each read takes 4 to 32 ms.

<div class="sowhat"><span class="label">So what</span> <b>Hours of warning against a 60-minute buffer.</b> 95 out of 100 alerts are real, so the crew trusts them.</div>

<!--
If the welder is not HIGH yet, point at the other HIGH stations first (natural degradation), then come back.
-->

---

## Demo ② Fix it in a planned break

<div class="meta"><b>7:00 to 9:00</b> · for both</div>

<div class="tell"><span class="label">Tell</span> "Now the part that pays: acting on it."</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com" target="_blank">Plant Health Live app</a> : create work order → complete it → watch the risk return to NORMAL</div>

- **One click** creates a P1 work order. It is a transactional Postgres write in Lakebase, about **12 ms**, and it streams back into the lakehouse for reporting.
- The technician completes it. The welder's risk drops back to **NORMAL** on the same screen, about 3 minutes later.

<div class="sowhat"><span class="label">So what</span> A <b>28-minute planned job</b> instead of a 112-minute emergency, and <b>about $6,300 less in parts</b>. No Aurora Elbil line stop: on this line, that would have cost <b>about $575,000</b>.</div>

<!--
While the risk recovers, move on to demo 3 and come back to show NORMAL.
-->

---

## Demo ③ Know the OEM exposure

<div class="meta"><b>9:00 to 11:00</b> · for Ingrid</div>

<div class="tell"><span class="label">Tell</span> "Ingrid, this is the question you'd ask before an OEM review."</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/genie/rooms/01f1c10d662111078cd7326dff1774c6?o=7474651880045550" target="_blank">Genie: Plant Maintenance Agent</a> : "Which OEM programs are exposed to a line stop right now?" · data: <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/oem_delivery_exposure?o=7474651880045550" target="_blank">pdm_ops.oem_delivery_exposure</a></div>

| Line | OEM program | Riskiest station | OEM stop if it fails | Risk-weighted exposure |
|---|---|---|---|---|
| PLT-S-B | Fjord Electric FE Pace Sedan | Stamping press, HIGH | 51 min | **$913k** |
| PLT-N-C | Nordvik Motors NV-e5 Crossover | Stamping press, HIGH | 51 min | **$609k** |
| PLT-E-A | Aurora Elbil A3 Hatch | Extrusion CNC, ELEVATED | 55 min | **$294k** |

*Snapshot from an earlier run; the live answer reflects today's risk.*

<div class="sowhat"><span class="label">So what</span> One governed view joins live risk to every OEM contract. <b>You walk into the Fjord Electric review knowing your exposure.</b> Genie was tested before anyone used it: 12 of 12 questions correct against reference SQL.</div>

---

## What it is worth to Volta

<div class="meta"><b>11:00 to 13:30</b> · for Ingrid · illustrative, Volta's finance team replaces the assumptions in the pilot</div>

<div class="two">
<div class="card"><h3>1 · Own P&amp;L</h3><div class="big">about $3.6M / yr</div>190 hours of line downtime avoided, plus parts, minus false-alarm inspections. About +0.26 OEE availability points, with no new equipment.</div>
<div class="card"><h3>2 · OEM charges avoided</h3><div class="big">about $4.0M / yr</div>If 5% of unplanned failures reach the OEM: about 10 stops × $595k, 70% avoided. At 2%: $1.6M. At 10%: $8.0M.</div>
<div class="card"><h3>3 · Next program award</h3><div class="big">decisive</div>A clean delivery scorecard with each OEM. Not monetized here.</div>
</div>

| How a Tier-1 COO is judged (Volta to confirm) | What moves |
|---|---|
| EBITDA margin after annual OEM price-downs | Layer 1, without more headcount |
| OEM charges and premium freight | Layer 2 |
| OEM scorecard and the next program award | Fewer line stops; exposure per OEM visible live |
| Capex and free cash flow | More output from the same 12 lines |

**For Bjørn's crew,** the people the app serves: planned repairs go from **20% to about 76%**, and repair minutes per job halve, **96 → 48**.

<!--
Assumptions: 2 unplanned failures per station per year, 70% converted into planned repairs, $15,000 per hour of internal line downtime. "Don't believe my numbers. Believe the method. The pilot replaces them with yours."
-->

---

## Demo ④ Under the hood: what Linnea's team would own

<div class="meta"><b>13:30 to 16:30</b> · for Linnea</div>

<div class="tell"><span class="label">Tell</span> "Linnea, here is how it is built, and what your team would run."</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/b5544be9-b72f-4e83-b029-1a7151fc53c1?o=7474651880045550" target="_blank">SDP pipeline</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/lakebase/projects/pdm-demo?o=7474651880045550" target="_blank">Lakebase project</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/endpoints/pdm-station-risk?o=7474651880045550" target="_blank">serving endpoint + AI Gateway</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/src/app" target="_blank">src/app</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/blob/main/databricks.yml" target="_blank">databricks.yml</a></div>

```
Sensors ──► Zerobus ──► SDP pipeline: clean + score every 10 s (UC model) ──► Delta ──► synced table, about 4 s
Bjørn's browser ◄── FastAPI on Databricks Apps ◄── Lakebase (Postgres)
                     ├─ work orders ──► Lakebase ──► Lakehouse Sync ──► Unity Catalog
                     ├─ what-if ──► Model Serving via AI Gateway
                     └─ questions ──► Genie Conversation API
```

| Concern | How it works | Measured |
|---|---|---|
| Data quality | Pipeline expectations drop invalid readings and count them | sensor to clean data in 3.9 s, to screen in about 60 s |
| Identity | The app's own service principal; Postgres tokens minted and refreshed in the pool | no secrets in code |
| Access | Least privilege; plant row filter enforced by the platform, proven on the app identity | 6 → 12 → 6 rows |
| Deploy and test | One bundle in Git per environment; an end-to-end test drives every API call (<a href="https://github.com/saschave-db/mfg-predictive-maintenance/blob/main/evidence/08_app/e2e_fault_injection.md" target="_blank">run log</a>) | deployed code = repo, by checksum |

<div class="sowhat"><span class="label">So what</span> No brokers, database servers or model hosts for Linnea's team to patch. <b>Ingrid: that keeps run cost and on-call small.</b></div>

<!--
Show the SDP pipeline graph and its data-quality tab first, then the Lakebase project, then the endpoint's AI Gateway settings, then the repo.
Name the limits before Linnea finds them: Genie runs as the app identity (per-viewer filtering needs on-behalf-of-user auth); the endpoint scales to zero, so the first call after idle took about 60 s; a few app settings are still hard-coded.
-->

---

## What we proved, and what we tell you up front

<div class="meta"><b>16:30 to 18:00</b> · for both · every number is an executed run, committed as text (<a href="https://github.com/saschave-db/mfg-predictive-maintenance#requirement--source--live-evidence" target="_blank">requirement → evidence matrix</a>)</div>

<div class="two">
<div class="card"><h3>Proven on the running system</h3>

- 271 of 271 failures flagged, about 4 operating hours ahead, 95% precision
- Live loop: fault → HIGH → work order → repair → NORMAL; the station never failed
- 96 stations at 1 Hz through Zerobus; 4 to 32 ms app reads; 12 ms work orders
- Genie 12 of 12; plant isolation proven on the app's identity

</div>
<div class="card"><h3>Honest limits</h3>

- Synthetic data and fictional contracts: the value model is illustrative until the pilot
- About 60 s to screen: right for this decision, not a safety interlock
- Alerts name the most deviating sensor, not a full root cause
- Per-viewer filtering in Genie needs on-behalf-of-user auth: a pilot add-on

</div>
</div>

<!--
Owning the limits is part of the pitch. Keep this slide short and move to the ask.
-->

---

## Pilot and the ask

<div class="meta"><b>18:00 to 20:00</b> · for both</div>

**90 days on line PLT-E-A** (Aurora Elbil A3 Hatch, Plant East)

| Weeks | What happens |
|---|---|
| 1 to 2 | Baseline: 12 months of failures, repair times, downtime cost, OEM charges |
| 3 to 5 | Connect the line's sensors through Zerobus; load the CMMS history and the JIS terms. Linnea's team deploys the bundle into Volta's workspace |
| 6 to 8 | Train on Volta's history; set the alert threshold with Bjørn |
| 9 to 12 | Bjørn's crew runs the alerts in shadow mode, then live |

**Success, agreed up front:** ≥ 70% of failures flagged with more than 60 minutes of warning · ≥ 80% alert precision · zero OEM stops from flagged stations · a measured drop in unplanned downtime

<div class="sowhat"><span class="label">The ask</span> <b>Ingrid:</b> sponsor the 90-day pilot on PLT-E-A. <b>Linnea:</b> a code walkthrough and the first deploy into your workspace next week.</div>

<!--
"Ingrid, will you sponsor it? Linnea, can we set up the walkthrough for next week?" Then stop talking and wait.
-->

---

<!-- _class: tiny -->

## Backup · demo launchpad (every component, live)

Links open in a new tab. Workspace: <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com?o=7474651880045550" target="_blank">fevm-serverless-stable-am1uc2</a>.

| Step | Open | What to show |
|---|---|---|
| Data generation + **Zerobus** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/16077621483238?o=7474651880045550" target="_blank">simulator job</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_raw/sensor_readings?o=7474651880045550" target="_blank">pdm_raw.sensor_readings</a> | Job running, 96 stations at 1 Hz. Table history: every write `engineInfo = Zerobus` |
| **SDP** pipeline | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/b5544be9-b72f-4e83-b029-1a7151fc53c1?o=7474651880045550" target="_blank">SDP pipeline</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/sensor_readings_clean?o=7474651880045550" target="_blank">pdm_core.sensor_readings_clean</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/station_risk_scores?o=7474651880045550" target="_blank">pdm_core.station_risk_scores</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/station_health_current?o=7474651880045550" target="_blank">pdm_core.station_health_current</a> | Graph, data-quality tab, lineage from the Zerobus table to the app |
| **ML** in Unity Catalog | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/models/serverless_stable_am1uc2_catalog/pdm_ml/station_failure_model?o=7474651880045550" target="_blank">UC model</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/experiments/2742082353844011?o=7474651880045550" target="_blank">MLflow experiment</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/269340780177784?o=7474651880045550" target="_blank">training job</a> | Version 2 = `@champion`, PR-AUC 0.91, lead time per failure mode |
| **Lakebase** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/5135c1d5-fce7-4893-898c-d902dc34a0ea?o=7474651880045550" target="_blank">synced-table pipeline</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_live/station_risk_scores?o=7474651880045550" target="_blank">pdm_live.station_risk_scores</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/lakebase/projects/pdm-demo?o=7474651880045550" target="_blank">Lakebase project</a> | Synced table about 4 s behind Delta; work orders as Postgres rows |
| **App** | <a href="https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com" target="_blank">Plant Health Live app</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/apps/pdm-plant-health-live?o=7474651880045550" target="_blank">app config</a> | Inject fault → HIGH → work order → NORMAL |
| **Model Serving** + AI Gateway | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/endpoints/pdm-station-risk?o=7474651880045550" target="_blank">serving endpoint + AI Gateway</a> | What-if from the app, usage tracking |
| **Genie** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/genie/rooms/01f1c10d662111078cd7326dff1774c6?o=7474651880045550" target="_blank">Genie: Plant Maintenance Agent</a> | OEM exposure question; benchmarks 12/12 |
| Governed KPIs | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/maintenance_metrics?o=7474651880045550" target="_blank">pdm_ops.maintenance_metrics</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/station_risk_metrics?o=7474651880045550" target="_blank">pdm_ops.station_risk_metrics</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/oem_delivery_exposure?o=7474651880045550" target="_blank">pdm_ops.oem_delivery_exposure</a> | One definition per KPI; OEM exposure joins live risk to JIS contracts |
| **Governance** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_raw/technicians?o=7474651880045550" target="_blank">pdm_raw.technicians</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/work_orders_current?o=7474651880045550" target="_blank">pdm_ops.work_orders_current</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/438031727317059?o=7474651880045550" target="_blank">governance job</a> | PII masks, plant row filter, tags, grants |
| Industry context | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/233410447833891?o=7474651880045550" target="_blank">industry context job</a> | OEM programs, JIS buffers, scorecard KPIs computed from history |
| Code and proof | <a href="https://github.com/saschave-db/mfg-predictive-maintenance" target="_blank">GitHub repo</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/blob/main/databricks.yml" target="_blank">databricks.yml</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/src/pipeline" target="_blank">src/pipeline</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/src/app" target="_blank">src/app</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/evidence" target="_blank">evidence/</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/755461157363253?o=7474651880045550" target="_blank">evidence notebooks job</a> | One bundle; executed notebooks with outputs |
| Deep dive | <a href="https://github.com/saschave-db/mfg-telemetry-dq-cicd" target="_blank">mfg-telemetry-dq-cicd</a> | Zerobus + Auto Loader, SQL expectations, quarantine, DQ gate, dev/staging/prod |

*Before demoing: start Lakebase, both pipelines, the simulator and the app; warm the serving endpoint and Genie once.*

---

<!-- _class: dense -->

## Backup · Bjørn's shift, before and after

| | Today | With the app |
|---|---|---|
| Finding out | When the line stops, and the JIS clock is already running | Hours ahead, ranked by risk, refreshed every few seconds |
| Knowing why | Diagnose on the spot | The alert names the top signal and how far it is off normal |
| Acting | Emergency call-out | One-click work order into the next planned break; in the pilot it flows into the CMMS |
| Planned share of repairs | 20% | about 76% |
| Repair minutes per job | 96 | about 48 |
| Alerts he can trust | none | 95% precision |

---

<!-- _class: tiny -->

## Backup · where the numbers come from

All figures are from executed runs, committed as text in <a href="https://github.com/saschave-db/mfg-predictive-maintenance" target="_blank">GitHub repo</a>. How the industry review gaps were closed: `docs/INDUSTRY_FIT.md`.

| Claim | Evidence |
|---|---|
| 271/271 failures flagged, median 244 s lead (about 4 operating hours), PR-AUC 0.91, precision 0.95 | `evidence/04_training/02_train_model.md` |
| 112 vs 28 min downtime, $7,200 vs $870 parts, 1,096 corrective vs 268 preventive repairs | `evidence/03_backfill/01_backfill_history.md` |
| OEM programs, JIS buffers, line-stop charges, exposure per line and per OEM, $595k average charge | `evidence/11_industry_context/05_industry_context.md` |
| Planned share, repair minutes, parts spend, layer 1 and 2 value, OEE points, sensitivity | `evidence/11_industry_context/05_industry_context.md`, "Scorecard KPIs", "Value model", "Sensitivity" |
| Live run on PLT-E-A03: fault, HIGH, work order, repair, NORMAL | `evidence/08_app/e2e_fault_injection.md`, `evidence/10_evidence_notebooks/E08_end_to_end.md` |
| 3.9 s to clean data, about 60 s to screen, 4 to 32 ms reads, 12 ms work orders | `evidence/06_live_pipeline/04_live_evidence.md`, `evidence/08_app/`, `evidence/10_evidence_notebooks/E04_lakebase.md` |
| Genie 12/12, including the OEM exposure questions | `evidence/07_genie/benchmark.md`, `evidence/10_evidence_notebooks/E06_genie.md` |
| Plant-level access on the app identity (6 → 12 → 6 rows) | `evidence/08_app/governance_as_app_sp.json`, `evidence/10_evidence_notebooks/E05_governance.md` |

**Layer 1:** 96 × 2 = 192 failures; 70% = 134 converted; 134 × 84.6 min = 189 h × $15k = $2.83M; 134 × $6,329 = $0.85M; false alarms ≈ 7 × $7.9k = $0.06M; net $3.62M. **Layer 2:** 192 × 5% = 9.6 OEM stops × 70% × $594,853 = $4.0M. **Maintenance KPIs:** 329 corrective + 1,035 planned: planned share 76%, repair minutes 48, parts $8.12M → $3.27M.

Volta Industrial, Nordvik Motors, Fjord Electric, Aurora Elbil and all personas are fictional, and so is all of the data.
