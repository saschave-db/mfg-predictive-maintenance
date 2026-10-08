---
marp: true
title: From failures to planned repairs. Live predictive maintenance on Databricks
paginate: true
---

# Turn unplanned failures into planned repairs

**Live predictive maintenance for discrete manufacturing, on one Databricks platform**

Audience: VP Manufacturing / COO (executive sponsor) and Head of Maintenance & Reliability (domain owner)

All data in this deck is synthetic. No customer data was used.

---

## The outcome in one slide

**Every failure in the test set was flagged before it happened. On average there were about 4 operating hours of warning.**

| Buyer KPI | What we showed | What it means for you |
|---|---|---|
| Unplanned failures caught early | **271 of 271** (100%) on a held-out time window | Stations get repaired, not rescued |
| Warning lead time | **Median about 4 operating hours** (244 s of compressed demo time) | Enough to plan the repair into the next break or shift change |
| Alert precision | **95%** at the HIGH-risk threshold | Crews trust the alerts. About 1 in 20 is a false alarm |
| Downtime per event | **28 min planned** vs **112 min unplanned** (4x less) | About 85 min of line time saved per avoided failure |
| Parts cost per event | **$870 planned** vs **$7,200 unplanned** (8x less) | About $6,300 saved per avoided failure |
| Illustrative value, 96-station fleet | **About $3.6M per year** (assumptions on slide 6) | Payback inside one pilot cycle |

In the live loop, the at-risk station was **repaired and never failed**.

---

## The problem, in your KPIs

Unplanned downtime is the biggest controllable loss in **OEE availability**.

- A failure stops the line. The repair is unplanned: parts get expedited, crews get pulled off other work, and the mean time to repair (MTTR) is long.
- The same fault caught early becomes a short, planned job.

From the synthetic maintenance history (24 h of 1 Hz data from 96 stations, 1,096 failures):

| Event type | Avg downtime | Avg parts cost |
|---|---|---|
| Corrective repair (after failure) | **112 min** | **$7,200** |
| Preventive repair (planned) | **28 min** | **$870** |

**So every failure you convert into a planned repair saves about 85 minutes of line time and about $6,300 in parts.**

The barrier is not data. Plants already have sensors. The barrier is turning raw telemetry into a **trusted, timely, actionable** signal for the people who own the repair.

---

## What we demonstrated, live

One station, one shift, end to end. Every step is logged as text in the repo.

1. **The fault starts.** A bearing begins to wear on a CNC mill. The sensors drift slowly. Nothing looks wrong to the eye.
2. **The risk rises.** The live screen shows the station's failure probability climbing. The **top signal** is vibration.
3. **The alert fires.** The station turns HIGH risk about 3 minutes after the fault starts, which is about 3 operating hours of compressed time.
4. **The supervisor acts.** One click in the app creates a work order and assigns a technician.
5. **The repair happens.** The technician completes the work order. The station's risk drops back to NORMAL.
6. **The station never failed.** No line stop and no expedited parts.
7. **The plant manager asks:** "Which stations in Plant North are most at risk right now?" The Genie agent answers in plain language from governed data.

Time is compressed in the demo: 1 demo minute is about 1 operating hour.

---

## Proven, not promised

Measured on the running system (sources in `evidence/`):

| Capability | Measured result |
|---|---|
| Sensor data streamed in | 96 stations at 1 Hz, about 96 rows/s, no Kafka to operate |
| Sensor to clean data | 3.9 s median |
| Sensor to risk score on the plant screen | about 60 s |
| App reads of live state | 4 to 32 ms |
| Work order write and read back | 12 to 14 ms |
| What-if scoring for an engineer | 41 to 140 ms |
| Plain-language answers (Genie) | 10 of 10 benchmark questions match the reference SQL |
| Plant-level data access | The app's identity sees only its own plant (6 of 18 rows). Personal data stays masked |

**About 60 s of latency against hours of warning is not the constraint.** Failures develop over hours. The decision window is the shift, not the second.

---

## Value model: illustrative 96-station fleet

These are assumptions to replace with your numbers in the pilot. The per-event savings come from the demo history (slide 3).

| Input | Value | Source |
|---|---|---|
| Stations | 96 (3 plants, 12 lines) | Demo fleet |
| Unplanned failures per station per year | 2 | **Assumption** (buyer input) |
| Share of failures converted to planned repairs | 70% | **Assumption**, below the 100% detection rate, to allow for crew availability |
| Line downtime cost | $15,000 per hour | **Assumption** (buyer input) |
| Downtime and parts saved per converted failure | 85 min, $6,300 | Demo history |

| Result per year | Value |
|---|---|
| Failures avoided | 134 of 192 |
| Line downtime avoided | **about 190 hours** |
| Downtime cost avoided | **about $2.8M** |
| Parts cost avoided | **about $0.85M** |
| False alarm cost (5% of alerts, each about a planned inspection) | about -$0.06M |
| **Net annual value** | **about $3.6M** |

---

## Sensitivity: the case holds under conservative inputs

Net annual value for the 96-station fleet, assuming 2 failures per station per year:

| Converted to planned \ Line cost | $5k / h | $15k / h | $50k / h |
|---|---|---|---|
| 50% | $1.3M | $2.6M | $7.3M |
| 70% | $1.8M | $3.6M | $10.2M |
| 90% | $2.3M | $4.7M | $13.1M |

- Value scales with the number of stations and with downtime cost per hour. High-volume lines (automotive, packaging, semiconductor) sit at the right of the table.
- Availability gain: about **190 of 360** unplanned downtime hours removed. That is **about +0.26 OEE availability points** across 12 lines that run 6,000 h per year.
- Not counted: avoided scrap, safety incidents, overtime, spare-parts inventory, and on-time delivery.

---

## For the executive sponsor: why this matters to you

**Availability and throughput.** You get a measurable OEE availability gain from the same assets, without capex on new lines.

**Cost.** Corrective maintenance becomes planned maintenance at about 1/8 of the parts cost and 1/4 of the downtime.

**Speed to value.** Everything runs on one platform with serverless components and no streaming middleware to operate. The pilot fleet is live in weeks, not quarters.

**Scale.** The same pipeline, model and governance roll out plant by plant. Each plant sees only its own data, which is enforced by the platform rather than by the app.

**Risk and audit.** Every number is traceable from sensor to decision: lineage, model version, access policy and who acted.

**What I need from you:** a pilot line, a named maintenance owner, and the baseline KPIs (slide 12).

---

## For the maintenance and reliability owner: your day changes

**Before**
- You find out about a failure when the line stops.
- Root cause gets reconstructed after the fact from logs in different systems.
- Preventive maintenance runs on a calendar. You over-maintain some assets and miss others.

**After**
- A live plant screen ranks stations by failure probability and names the **top signal** (vibration, temperature or pressure).
- One click creates the work order. It is stored transactionally and flows back to analytics automatically.
- Ask in plain language: "Open work orders by plant", "Mean time to repair this week", "Which failure mode costs us the most downtime?"
- Engineers run what-if checks: "If vibration rises 20%, what is the risk?" The answer comes back in under 150 ms.
- The repair is confirmed in the data. The risk returns to NORMAL, and you see that the fix worked.

**KPIs you own that move:** MTTR, planned maintenance percentage, unplanned downtime hours, alert precision, and warning lead time.

---

## How it works (one platform, no glue)

```
Station sensors ──► Zerobus streaming ingest ──► Clean + score in-stream ──► Live plant screen
                    (no Kafka to run)              (failure model, every 10 s)     (Databricks App)
                                                          │                          │ work orders
                                                          ▼                          ▼
                                   Unity Catalog: governed KPIs ◄──── Lakebase (operational database)
                                          │
                                          ▼
                                 Genie agent: plain-language answers
```

| Piece | Business role |
|---|---|
| Lakeflow Connect Zerobus | Plant gateways push data directly into governed tables |
| Spark Declarative Pipelines | Data-quality rules drop bad readings. Scoring runs continuously |
| ML model in Unity Catalog | One versioned model for streaming scores and engineer what-ifs |
| Lakebase | Millisecond reads for the screen and transactional work orders |
| Genie agent | Self-service answers for plant leaders on certified KPIs |
| Databricks App | The front end for supervisors and technicians |

---

## Why operations can trust it

- **Data quality is enforced, not hoped for.** Pipeline expectations drop invalid sensor readings and count them visibly.
- **Explainable alerts.** Each alert names the sensor that drives it. Crews know where to look.
- **Access by plant.** A plant's team sees only its plant. This was proven on the app's own identity, not on an admin account. Technician contact details are masked.
- **One definition of each KPI.** Genie, dashboards and the app use the same governed metric definitions. There is no spreadsheet drift.
- **Auditable.** Lineage from sensor to screen, model versions, work-order history and every model call are tracked.
- **Validated before release.** Genie passed a 10-question benchmark against reference SQL before any user touched it.

---

## Pilot plan: 90 days, measured in your KPIs

| Phase | Weeks | Deliverable |
|---|---|---|
| Baseline | 1 to 2 | Pick one line (8 to 20 stations). Capture 12 months of failures, MTTR, downtime cost and PM schedule |
| Connect | 3 to 5 | Stream the line's sensors through Zerobus. Load the maintenance history from your CMMS |
| Model | 6 to 8 | Train on your failure history. Agree the alert threshold with the maintenance owner |
| Operate | 9 to 12 | Run alerts in shadow mode, then live. Work orders flow back to your CMMS |

**Success criteria, agreed up front:**
- At least 70% of failures flagged with at least 2 hours of warning
- Alert precision of at least 80%
- Measured reduction in unplanned downtime hours on the pilot line against the baseline
- A business case for the next plant, built from pilot data rather than assumptions

---

## What we are honest about

- **The demo uses synthetic data.** Real failure signatures are noisier. That is why the pilot retrains on your history.
- **The value model on slides 6 and 7 is illustrative.** Failure frequency and downtime cost are your inputs, not ours.
- **About 60 s from sensor to screen.** That is right for failures that develop over hours. It is not a safety interlock and does not replace machine protection.
- **Recovery shows about 3 minutes after a repair**, while the model's window refills with healthy data.
- **Alert explanations are simple.** They name the sensor that deviates most, not a full root-cause analysis.
- **Data access applies at the app level today.** Per-user filtering for each viewer is a pilot add-on.

---

## The ask

1. **Sponsor:** approve a 90-day pilot on one line and name a maintenance owner.
2. **Domain owner:** share 12 months of failure and work-order history and the current PM schedule.
3. **Together:** agree the baseline and the success criteria on slide 12 before day 1.

**The outcome we commit to measure:** fewer unplanned stops, shorter repairs, lower parts spend, and a fleet-wide business case built from your own data.

---

## Appendix: where the numbers come from

All figures are from executed runs, committed as text in this repo.

| Claim | Evidence |
|---|---|
| 271/271 failures flagged, median 244 s lead, PR-AUC 0.91, precision 0.95 | `evidence/04_training/02_train_model.md` |
| 112 vs 28 min downtime, $7,200 vs $870 parts | `evidence/03_backfill/01_backfill_history.md` (maintenance log summary) |
| Fault to HIGH to repair to NORMAL, station never failed | `evidence/10_evidence_notebooks/E08_end_to_end.md`, `evidence/08_app/e2e_fault_injection.md` |
| 3.9 s to clean data, about 60 s to the screen | `evidence/06_live_pipeline/04_live_evidence.md`, `evidence/08_app/` |
| 4 to 32 ms app reads, 12 to 14 ms work order round trips | `evidence/08_app/e2e_fault_injection.md`, `evidence/10_evidence_notebooks/E04_lakebase.md` |
| Genie 10/10 | `evidence/07_genie/benchmark.md`, `evidence/10_evidence_notebooks/E06_genie.md` |
| Plant-level access on the app identity (6 → 12 → 6 rows) | `evidence/08_app/governance_as_app_sp.json`, `evidence/10_evidence_notebooks/E05_governance.md` |

**Value model arithmetic (slide 6):** 96 × 2 = 192 failures. 70% = 134 converted. 134 × 84.6 min = 189 h × $15k = $2.83M. 134 × $6,329 = $0.85M. False alarms: 134 / 0.95 − 134 ≈ 7, at about $7.9k each (planned job plus 28 min of line time) = $0.06M. Net = $3.62M.
