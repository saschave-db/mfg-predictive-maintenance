---
marp: true
theme: volta
title: Volta Industrial. Never stop the OEM line. Live predictive maintenance for EV battery enclosures on Databricks
paginate: true
---

<!-- _class: title -->

# Volta Industrial: never be the supplier that stops the OEM line

**Live predictive maintenance for aluminum EV battery enclosures, on one Databricks platform**

For **Alex**, executive sponsor, and **Shreya**, who would own and run the solution

*20 minutes · all companies, people and data are fictional and synthetic*

<!--
"Thanks, Alex. Thanks, Shreya. Let me start with something that happened on one of your lines."
-->

---

<!-- _class: hook -->

## 6:12 on a Tuesday, Plant East

<div class="meta"><b>0:00 to 1:00</b> · the hook</div>

<div class="story">
The frame welder on the Aurora Elbil line has been running hot for hours. Nobody sees it. At 6:12 it trips.<br>
Bjørn, the maintenance supervisor, gets the call. The repair takes <b>112 minutes</b>. The JIS buffer to Aurora's assembly line lasts <b>60</b>.<br>
Aurora's line stands still for 52 minutes. The contract charge is about <b>$575,000</b>. And Volta gets a mark on the scorecard that decides the next vehicle program.
</div>

**What we found in your maintenance history:** 4 out of 5 repairs are emergencies like this one. Every unplanned repair (112 min) is longer than every buffer you have (45 to 90 min).

<div class="sowhat"><span class="label">The question</span> What if Bjørn had known <b>four hours earlier</b>, and fixed it in a planned 28-minute break?</div>

<!--
Tell it as a story, slowly. Pause after "it trips" and after "$575,000".
-->

---

## Why keep listening: the value, and today's roadmap

<div class="meta"><b>1:00 to 3:00</b> · value first, then the roadmap · illustrative, your finance team replaces the assumptions in the pilot</div>

<div class="two">
<div class="card"><h3>Own P&amp;L</h3><div class="big">about $3.6M / yr</div>190 hours less line downtime, fewer expedited parts</div>
<div class="card"><h3>OEM charges avoided</h3><div class="big">about $4.0M / yr</div>if 5% of failures reach the OEM (2%: $1.6M; 10%: $8.0M)</div>
<div class="card"><h3>Warning before a failure</h3><div class="big">about 4 hours</div>271 of 271 test failures caught, 95% of alerts real</div>
</div>

<div class="road">
<div><b>① See it coming, fix it in a break</b>Bjørn's app, live on the Aurora Elbil line</div>
<div><b>② Know your exposure</b>Which OEM contract is at risk right now, in plain language</div>
<div><b>③ Run it safely in production</b>How it is built, deployed, secured and owned</div>
</div>

<div class="ask"><span class="label">Check in</span> "Alex, Shreya: does this match what you want to get out of today? Anything you'd add?"</div>

<!--
Assumptions behind the value: 2 unplanned failures per station per year, 70% converted into planned repairs, $15,000 per hour of internal downtime.
Listen to the answers. If Alex says "risk" or "chargebacks", lean on topic 2. If Shreya says "operations" or "security", lean on topic 3.
In the background: inject the overheating fault on PLT-E-A03 in the app now, so it is HIGH when topic 1 starts.
-->

---

## ① See it coming, fix it in a planned break: Tell

<div class="meta"><b>3:00 to 4:00</b> · before the demo · for both</div>

<div class="tell"><span class="label">Today on the shop floor</span> Bjørn finds out when the line stops. His crew diagnoses on the spot while the JIS clock runs. Preventive maintenance follows a calendar, so it is too early for some stations and too late for others.</div>

**What I'll highlight:** one station, PLT-E-A03, the frame welder on the Aurora Elbil line (60-minute buffer). In the demo, one minute is about one operating hour.

| Step | What you'll see |
|---|---|
| 1 | The welder's risk climbs from green to **HIGH** |
| 2 | The screen tells Bjørn **why**: which sensor, and how far off normal |
| 3 | **One click** creates the work order for a planned break |
| 4 | The repair is done, and the risk returns to **NORMAL** |

---

## ① See it coming, fix it in a planned break: Show, then Tell

<div class="meta"><b>4:00 to 8:30</b> · the demo · for both</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com" target="_blank">Plant Health Live app</a></div>

- **Step 1 to 2:** the welder goes from about 1% to HIGH (79%, then 99%). The top signal is motor current, 10% above normal.
- **Step 3:** one click creates a P1 work order. The screen answers in milliseconds, so Bjørn decides fast, with no waiting and no re-typing.
- **Step 4:** the technician completes it, and the risk returns to NORMAL on the same screen.

<div class="sowhat"><span class="label">So what</span> Bjørn's team gets <b>hours of warning instead of an emergency stop</b>: a 28-minute planned job instead of 112 minutes, about $6,300 less in parts, and no $575,000 Aurora line stop.</div>

<div class="ask"><span class="label">Ask Shreya</span> "Shreya, if your team owned this app, who would be the first call when Bjørn says the screen looks wrong? Let's make sure that's covered in topic 3."</div>

<!--
While the risk recovers, move on and come back to show NORMAL.
-->

---

## ② Know your exposure

<div class="meta"><b>8:30 to 11:30</b> · Tell, Show, Tell · for Alex</div>

<div class="tell"><span class="label">Tell</span> "Today, before an OEM review, someone builds a spreadsheet of which lines are at risk. It's out of date when it's printed. I'll ask one question in plain language and get the answer from live data."</div>

<div class="show"><span class="label">Show</span> ▶ <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/genie/rooms/01f1c10d662111078cd7326dff1774c6?o=7474651880045550" target="_blank">Genie: Plant Maintenance Agent</a> : "Which OEM programs are exposed to a line stop right now?"</div>

| Line | OEM program | Riskiest station | OEM stop if it fails | Risk-weighted exposure |
|---|---|---|---|---|
| PLT-S-B | Fjord Electric FE Pace Sedan | Stamping press, HIGH | 51 min | **$913k** |
| PLT-N-C | Nordvik Motors NV-e5 Crossover | Stamping press, HIGH | 51 min | **$609k** |
| PLT-E-A | Aurora Elbil A3 Hatch | Extrusion CNC, ELEVATED | 55 min | **$294k** |

*Earlier snapshot; the live answer reflects today's risk.* The answer comes from one governed view (<a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/oem_delivery_exposure?o=7474651880045550" target="_blank">pdm_ops.oem_delivery_exposure</a>). Genie answered 12 of 12 test questions correctly before anyone used it.

<div class="sowhat"><span class="label">So what</span> <b>You walk into the Fjord Electric review knowing your exposure</b>, and Bjørn's crew works the riskiest line first. Fewer stops, fewer charges.</div>

<div class="ask"><span class="label">Ask Alex</span> "Alex, which OEM relationship worries you most right now? That's the line I'd pick for the pilot."</div>

---

## ③ Run it safely in production: how it works

<div class="meta"><b>11:30 to 14:00</b> · Tell, Show, Tell · for Shreya</div>

<div class="tell"><span class="label">Tell</span> "Shreya, your questions are who runs it, what breaks, and how it's secured. First the flow, one benefit per step. Then the path to production."</div>

<div class="flow">
<div><b>Plant gateways</b>push sensor data directly, no message broker to run</div><span>→</span>
<div><b>Pipeline</b>cleans every reading and scores every station every 10 s</div><span>→</span>
<div><b>Operational database</b>serves Bjørn's screen in milliseconds and stores work orders</div><span>→</span>
<div><b>App</b>one screen for the crew, one question box for leadership</div>
</div>

**Sensor data reaches Bjørn's screen in under a minute.** Failures build over hours, so the decision window is the next planned break.

<div class="show"><span class="label">Show</span> ▶ <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/b5544be9-b72f-4e83-b029-1a7151fc53c1?o=7474651880045550" target="_blank">pipeline</a> (data-quality tab) · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/lakebase/projects/pdm-demo?o=7474651880045550" target="_blank">operational database (Lakebase)</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/endpoints/pdm-station-risk?o=7474651880045550" target="_blank">model endpoint + AI Gateway</a></div>

<div class="sowhat"><span class="label">So what</span> Every part is a managed service: <b>no brokers, database servers or model hosts for Shreya's team to patch</b>. Alex: that keeps run cost and on-call small.</div>

<!--
Do not name every component in one breath. Point at the four boxes, one benefit each.
If Shreya asks for the names: Zerobus, Spark Declarative Pipelines, Lakebase (managed Postgres), Databricks Apps, Model Serving with AI Gateway, Genie.
Lakebase, feature to value: 4 to 32 ms reads, so the screen feels instant, so Bjørn decides faster with less friction.
-->

---

<!-- _class: dense -->

## ③ Run it safely in production: code to prod, security, ownership

<div class="meta"><b>14:00 to 17:00</b> · for Shreya, answer this even if she doesn't ask</div>

<div class="two">
<div class="card"><h3>From code to production</h3>

- **Deploy:** pipeline, jobs (including the Zerobus target setup), app and model endpoint are one bundle in Git; the Lakebase synced table is one CLI step today (<a href="https://github.com/saschave-db/mfg-predictive-maintenance/blob/main/databricks.yml" target="_blank">databricks.yml</a>)
- **Promote:** CI/CD validates the bundle, deploys to test, runs an end-to-end test and a data-quality gate, then promotes to prod after approval
- **Proven:** <a href="https://github.com/saschave-db/mfg-telemetry-dq-cicd" target="_blank">mfg-telemetry-dq-cicd</a> runs dev → staging with the gate. A bad build failed it, so it never reached prod
- **Roll back:** redeploy the previous bundle version, or move the model's `@champion` alias back
- **Bad data and drift:** expectations drop and count bad readings; Zerobus rejects records that don't match the table; for file sources, quarantine keeps bad rows and schema changes are rescued, not crashed

</div>
<div class="card"><h3>Security and integration</h3>

- **Access:** Unity Catalog grants per identity; plant row filters, proven on the app's identity (6 → 12 → 6 rows)
- **PII:** technician contact data masked
- **Secrets:** in secret scopes, never in code; the app's credentials are injected by the platform
- **Identity:** SSO and SCIM from your identity provider
- **Network:** private connectivity from plant gateways to the workspace, designed with your network team in the pilot
- **CMMS:** work orders already flow into the lakehouse; the pilot adds the push into your CMMS

</div>
</div>

**On-call:** pipeline failures and an hourly data-quality monitor alert by email, or to Teams through a notification destination. Your team owns the app code; the platform runs the infrastructure.

<div class="ask"><span class="label">Ask Shreya</span> "Shreya, does this fit how your team ships today, or is there a step in your release process we should plug into?"</div>

<!--
This is the slide the last session missed. Cover the left column in 60 seconds, the right in 60, then ask Shreya.
Limits to name before she finds them: Genie runs as the app identity, so per-viewer filtering needs on-behalf-of-user auth; the model endpoint scales to zero, and its first call after idle took about 60 s; a few app settings are still hard-coded.
-->

---

## How sure can you be? Proof, and the honest limits

<div class="meta"><b>17:00 to 18:30</b> · for both · every number is an executed run (<a href="https://github.com/saschave-db/mfg-predictive-maintenance#requirement--source--live-evidence" target="_blank">requirement → evidence matrix</a>)</div>

<div class="ask"><span class="label">If asked about synthetic data, answer now</span> "Fair question. The model was tested on a later time window it never saw. In the pilot it retrains on your history, we validate the failure patterns with your engineers, and shadow mode is the go/no-go gate before any alert goes live."</div>

<div class="two">
<div class="card"><h3>Proven on the running system</h3>

- 271 of 271 failures flagged, about 4 operating hours ahead, 95% precision
- The live loop: fault → HIGH → work order → repair → NORMAL; the station never failed
- 96 stations at 1 Hz; reads in 4 to 32 ms; work orders in 12 ms
- Genie 12 of 12; plant isolation proven

</div>
<div class="card"><h3>Honest limits</h3>

- Synthetic data and fictional contracts: the value is illustrative until the pilot
- About 60 s to screen: right for this decision, not a safety interlock
- Alerts name the most deviating sensor, not a full root cause

</div>
</div>

<div class="sowhat"><span class="label">So what</span> You don't have to trust our numbers. <b>The pilot proves them on your line, behind a shadow-mode gate.</b></div>

<!--
Never defer this question. Give the short answer in the moment, then say: "I'll show the full proof at the end."
-->

---

## Pilot and the ask

<div class="meta"><b>18:30 to 20:00</b> · for both</div>

**90 days on one line, PLT-E-A** (Aurora Elbil A3 Hatch, Plant East)

| Weeks | What happens |
|---|---|
| 1 to 2 | Baseline: 12 months of failures, repair times, downtime cost, OEM charges |
| 3 to 5 | Connect the line's sensors; load CMMS history and JIS terms; Shreya's team deploys the bundle into your workspace |
| 6 to 8 | Train on your history; validate the patterns with your engineers; set the alert threshold with Bjørn |
| 9 to 12 | **Shadow mode** first, as the go/no-go gate, then live alerts |

**Success, agreed up front:** at least 70% of failures flagged with more than 60 minutes of warning · at least 80% alert precision · zero OEM stops from flagged stations · a measured drop in unplanned downtime

<div class="sowhat"><span class="label">The ask</span> <b>Alex:</b> sponsor the 90-day pilot on PLT-E-A. <b>Shreya:</b> a code walkthrough and the first deploy into your workspace next week.</div>

<!--
"Alex, will you sponsor it? Shreya, can we set up the walkthrough next week?" Then stop talking and wait.
-->

---

<!-- _class: tiny -->

## Backup · demo launchpad (every component, live)

Links open in a new tab. Workspace: <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com?o=7474651880045550" target="_blank">fevm-serverless-stable-am1uc2</a>.

| Step | Open | What to show |
|---|---|---|
| Data generation + **Zerobus** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/16077621483238?o=7474651880045550" target="_blank">simulator job</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_raw/sensor_readings?o=7474651880045550" target="_blank">pdm_raw.sensor_readings</a> | Job running, 96 stations at 1 Hz. Table history: every write `engineInfo = Zerobus` |
| **SDP** pipeline | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/b5544be9-b72f-4e83-b029-1a7151fc53c1?o=7474651880045550" target="_blank">pipeline</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/sensor_readings_clean?o=7474651880045550" target="_blank">pdm_core.sensor_readings_clean</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/station_risk_scores?o=7474651880045550" target="_blank">pdm_core.station_risk_scores</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_core/station_health_current?o=7474651880045550" target="_blank">pdm_core.station_health_current</a> | Graph, data-quality tab, lineage from the Zerobus table to the app |
| **ML** in Unity Catalog | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/models/serverless_stable_am1uc2_catalog/pdm_ml/station_failure_model?o=7474651880045550" target="_blank">UC model</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/experiments/2742082353844011?o=7474651880045550" target="_blank">MLflow experiment</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/269340780177784?o=7474651880045550" target="_blank">training job</a> | Version 2 = `@champion`, PR-AUC 0.91, lead time per failure mode |
| **Lakebase** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/pipelines/5135c1d5-fce7-4893-898c-d902dc34a0ea?o=7474651880045550" target="_blank">synced-table pipeline</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_live/station_risk_scores?o=7474651880045550" target="_blank">pdm_live.station_risk_scores</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/lakebase/projects/pdm-demo?o=7474651880045550" target="_blank">operational database (Lakebase)</a> | Synced table about 4 s behind Delta; work orders as Postgres rows |
| **App** | <a href="https://pdm-plant-health-live-7474651880045550.aws.databricksapps.com" target="_blank">Plant Health Live app</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/apps/pdm-plant-health-live?o=7474651880045550" target="_blank">app config</a> | Inject fault → HIGH → work order → NORMAL |
| **Model Serving** + AI Gateway | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/ml/endpoints/pdm-station-risk?o=7474651880045550" target="_blank">model endpoint + AI Gateway</a> | What-if from the app, usage tracking |
| **Genie** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/genie/rooms/01f1c10d662111078cd7326dff1774c6?o=7474651880045550" target="_blank">Genie: Plant Maintenance Agent</a> | OEM exposure question; benchmarks 12/12 |
| Governed KPIs | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/maintenance_metrics?o=7474651880045550" target="_blank">pdm_ops.maintenance_metrics</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/station_risk_metrics?o=7474651880045550" target="_blank">pdm_ops.station_risk_metrics</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/oem_delivery_exposure?o=7474651880045550" target="_blank">pdm_ops.oem_delivery_exposure</a> | One definition per KPI; OEM exposure joins live risk to JIS contracts |
| **Governance** | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_raw/technicians?o=7474651880045550" target="_blank">pdm_raw.technicians</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/explore/data/serverless_stable_am1uc2_catalog/pdm_ops/work_orders_current?o=7474651880045550" target="_blank">pdm_ops.work_orders_current</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/438031727317059?o=7474651880045550" target="_blank">governance job</a> | PII masks, plant row filter, tags, grants |
| Industry context | <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/233410447833891?o=7474651880045550" target="_blank">industry context job</a> | OEM programs, JIS buffers, scorecard KPIs computed from history |
| Code and proof | <a href="https://github.com/saschave-db/mfg-predictive-maintenance" target="_blank">GitHub repo</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/blob/main/databricks.yml" target="_blank">databricks.yml</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/src/pipeline" target="_blank">src/pipeline</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/src/app" target="_blank">src/app</a> · <a href="https://github.com/saschave-db/mfg-predictive-maintenance/tree/main/evidence" target="_blank">evidence/</a> · <a href="https://fevm-serverless-stable-am1uc2.cloud.databricks.com/jobs/755461157363253?o=7474651880045550" target="_blank">evidence notebooks job</a> | One bundle; executed notebooks with outputs |
| CI/CD and data quality | <a href="https://github.com/saschave-db/mfg-telemetry-dq-cicd" target="_blank">mfg-telemetry-dq-cicd</a> | Zerobus + Auto Loader, SQL expectations, quarantine, DQ gate, dev → staging → prod |

*Before demoing: start Lakebase, both pipelines, the simulator and the app; warm the serving endpoint and Genie once.*

---

<!-- _class: dense -->

## Backup · the value in detail

| How an executive sponsor at a Tier-1 supplier is judged (Volta to confirm) | What moves |
|---|---|
| EBITDA margin after annual OEM price-downs | about $3.6M a year from less downtime and fewer expedited parts, no extra headcount |
| OEM charges and premium freight | about $4.0M a year if 5% of failures reach the OEM (2%: $1.6M; 10%: $8.0M) |
| OEM scorecard and the next program award | fewer line stops; exposure per OEM visible live |
| Capex and free cash flow | about +0.26 OEE availability points from the same 12 lines |

| Bjørn's crew | Today | With 70% of failures caught |
|---|---|---|
| Planned share of repairs | 20% | about 76% |
| Repair minutes per job | 96 | about 48 |
| Alerts they can trust | none | 95% precision |

Assumptions: 2 unplanned failures per station per year, 70% converted into planned repairs, $15,000 per hour of internal line downtime, $595k average OEM charge per stop.

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
| Promotion dev → staging with an integration test and DQ gate; a bad build blocked | <a href="https://github.com/saschave-db/mfg-telemetry-dq-cicd" target="_blank">mfg-telemetry-dq-cicd</a>, `evidence/` |

**Layer 1:** 96 × 2 = 192 failures; 70% = 134 converted; 134 × 84.6 min = 189 h × $15k = $2.83M; 134 × $6,329 = $0.85M; false alarms ≈ 7 × $7.9k = $0.06M; net $3.62M. **Layer 2:** 192 × 5% = 9.6 OEM stops × 70% × $594,853 = $4.0M. **Maintenance KPIs:** 329 corrective + 1,035 planned: planned share 76%, repair minutes 48, parts $8.12M → $3.27M.

Volta Industrial, Nordvik Motors, Fjord Electric, Aurora Elbil and all personas are fictional, and so is all of the data.
