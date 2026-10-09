---
marp: true
title: Volta Industrial. Never stop the OEM line. Live predictive maintenance for EV battery enclosures on Databricks
paginate: true
---

# Volta Industrial: never be the supplier that stops the OEM line

**Live predictive maintenance for aluminum EV battery enclosure lines, on one Databricks platform**

Volta Industrial is a Tier-1 automotive supplier. It builds battery trays, battery covers and cooling plates for three EV makers: Nordvik Motors, Fjord Electric and Aurora Elbil. It ships them just-in-sequence from 12 lines in three plants.

Prepared for Ingrid Solberg (COO, executive sponsor) and Henrik Lindqvist (Head of Maintenance & Reliability, domain owner)

All companies, people and data in this deck are fictional and synthetic. No real customer data was used.

---

## Who this is for

| Persona | Role at Volta Industrial | What they are judged on |
|---|---|---|
| **Ingrid Solberg** | COO, executive sponsor | EBITDA margin under OEM price-downs, OEM scorecards that decide the next program award, capex and cash |
| **Henrik Lindqvist** | Head of Maintenance & Reliability, domain owner | Unplanned downtime hours, MTTR, planned maintenance share, maintenance cost against budget |
| **Astrid Nygård** | Plant Manager, Plant East | Plant OEE, JIS delivery performance to Aurora Elbil and Nordvik Motors, and scrap |
| **Bjørn Halvorsen** | Maintenance Supervisor, Plant East | Keeping the line inside its JIS buffer. Sending the right technician to the right station |
| **Sigrid Dahl** | Maintenance Technician | A clear work order that says what is wrong and where to look |

---

## The outcome in one slide

**Every failure in the test set was flagged before it happened, with a median of about 4 operating hours of warning. Volta's JIS buffers are only 45 to 90 minutes. About 240 minutes of warning gives the crew time to act well before a buffer would run out.**

| Volta KPI | What we showed | What it means for Volta |
|---|---|---|
| Failures caught before they stop the line | **271 of 271** on a held-out time window | Repairs get planned before the JIS buffer runs out |
| Warning lead time | **Median about 4 operating hours** | Enough to fix the station in a planned break. The OEM never notices |
| Alert precision | **95%** at the HIGH-risk threshold | Crews trust the alerts. About 1 in 20 is a false alarm |
| Planned maintenance share | **20% today → about 76%** at 70% conversion | Repairs move from emergency to plan |
| Mean repair time per event | **96 min → about 48 min** | Half the repair minutes per maintenance event |
| OEM line-stop charge per unplanned failure | **About $595,000** on average (Volta's synthetic contracts) | One avoided OEM line stop pays for the program |
| Illustrative annual value | **About $3.6M internal + about $4.0M OEM charges avoided** | Assumptions on the value slides |

In the live run, the at-risk welding station was **repaired and never failed**.

---

## Volta's market: why uptime is a competitive weapon

EV battery enclosures are a hard niche inside automotive supply. Five pressures shape every decision at Volta:

1. **Just-in-sequence delivery.** Enclosures are large, model-specific and built to the OEM's sequence. Volta holds only 45 to 90 minutes of buffer per line. If a station is down longer, the OEM's assembly line stops.
2. **Contract line-stop charges.** Volta's OEM contracts charge $8,000 to $18,000 for every minute the OEM line stands still. This is synthetic, but shaped like real automotive supply terms.
3. **Annual price-downs.** OEM contracts typically require price cuts every year. Margin has to come from the shop floor, not from price.
4. **Scorecards decide the next award.** OEMs rate each supplier on delivery, quality and launch. One line-stop event can cost the next vehicle program.
5. **Safety-critical, high-value parts.** The enclosure protects the battery in a crash and must stay sealed. A degrading welder or sealing robot puts weld integrity and leak tightness at risk, and scrapped aluminum parts are expensive.

**Differentiation:** Volta wants to win the next programs as the enclosure supplier that never stops an OEM line. Predictive maintenance makes that a measurable promise.

---

## The battery enclosure line, and where it fails

Every Volta line runs the same 8-station flow. The demo models each station and its failure modes.

| # | Process step | Station | Critical quality characteristic | Failure mode modeled |
|---|---|---|---|---|
| 1 | Stamping of tray floor and side members | Press | Dimensional accuracy | Hydraulic seal leak |
| 2 | Machining of extrusion profiles | CNC | Hole position for module mounting | Spindle bearing wear, overheating |
| 3 | Friction-stir welding of the frame | Welder | Weld seam integrity (crash load path) | Overheating |
| 4 | Sealant dispensing and handling | Robot | Bead continuity (IP67 sealing) | Joint bearing wear, overheating |
| 5 | Transfer to leak test | Conveyor | Takt and part sequence | Roller bearing wear |
| 6 | Flatness machining of cooling interface | CNC | Flatness of thermal interface | Spindle bearing wear, overheating |
| 7 | Laser welding of cover brackets | Welder | Weld penetration | Overheating |
| 8 | Clinching and end-of-line press | Press | Joint strength before JIS shipment | Hydraulic seal leak |

The line is serial. **Any one station down longer than the JIS buffer stops the OEM.**

---

## Volta's problem, in its own numbers

From Volta's synthetic maintenance history (96 stations, 1,096 failures):

| Event type | Avg downtime | Avg parts cost |
|---|---|---|
| Corrective repair (after failure) | **112 min** | **$7,200** |
| Preventive repair (planned) | **28 min** | **$870** |

- **Only 20% of repairs are planned today.** The rest happen after the station has already failed.
- **112 minutes is longer than every JIS buffer** Volta has (45 to 90 min). On average, an unplanned failure stops the OEM's line for **about 44 minutes**. Under Volta's contracts, that costs **about $595,000**.
- **A 28-minute planned repair fits inside every buffer.** The OEM never sees it.

**Turning a failure into a planned repair does more than save 85 minutes and $6,300. It turns an OEM line stop into a non-event.**

---

## What we demonstrated, live

Station PLT-E-A03 is the friction-stir welder on line PLT-E-A in Plant East. The line builds battery trays for the Aurora Elbil A3 Hatch, with a 60-minute JIS buffer. Every step is logged as text in the repo.

1. **The fault starts.** The welder starts to overheat. A hot weld tool also threatens weld seam integrity. Nothing looks wrong to the eye.
2. **The risk rises.** Bjørn's live plant screen shows the station's failure probability climbing. The **top signal** is the welder's motor current, running about 10% above normal.
3. **The alert fires.** The station turns HIGH risk about 4 minutes after the fault starts, seen in the app. In operating time, that is hours before it would fail.
4. **Bjørn acts.** One click creates a P1 work order for Sigrid.
5. **Sigrid repairs it.** She completes the work order. The risk drops back to NORMAL.
6. **The station never failed.** The Aurora Elbil line never stopped. That avoided a contract charge of about $575,000 for this line.
7. **Astrid asks Genie:** "Which OEM programs are exposed to a line stop right now?" Genie ranks the lines by risk-weighted exposure, with the OEM, program, riskiest station and minutes beyond the buffer.

Time is compressed in the demo: 1 demo minute is about 1 operating hour.

---

## Risk in the COO's language: OEM delivery exposure

The demo joins live failure risk to each line's OEM contract. One governed view answers: "If the riskiest station on this line fails now, does the OEM line stop, and what does it cost us?"

Snapshot from the running system (Genie answer, reproduced in SQL):

| Line | OEM program | Riskiest station | Risk | OEM stop if it fails | Risk-weighted exposure |
|---|---|---|---|---|---|
| PLT-S-B | Fjord Electric FE Pace Sedan | Stamping press (PLT-S-B01) | HIGH, 99.7% | 51 min | **$913k** |
| PLT-N-C | Nordvik Motors NV-e5 Crossover | Stamping press (PLT-N-C01) | HIGH, 99.9% | 51 min | **$609k** |
| PLT-E-A | Aurora Elbil A3 Hatch | Extrusion CNC (PLT-E-A02) | ELEVATED, 48% | 55 min | **$294k** |

- **Per OEM:** Fjord Electric $1.09M, Nordvik Motors $0.80M, Aurora Elbil $0.46M of risk-weighted exposure.
- This is the list Ingrid takes into the OEM review, and the order in which Henrik sends his crews.
- Genie passed 12 of 12 benchmark questions, including the two new OEM-exposure questions.

---

## Proven, not promised

Measured on the running system (sources in `evidence/`):

| Capability | Measured result |
|---|---|
| Sensor data streamed in | 96 stations at 1 Hz, about 96 rows/s, no Kafka to operate |
| Sensor to clean data | 3.9 s median |
| Sensor to risk score on the plant screen | about 60 s, against hours of warning and 45 to 90 min of buffer |
| App reads of live state | 4 to 32 ms |
| Work order write and read back | 12 to 14 ms |
| What-if scoring for an engineer | 41 to 140 ms |
| Plain-language answers (Genie) | 12 of 12 benchmark questions match the reference SQL |
| Plant-level data access | Proven on the app's own identity: it sees only its plant's rows. Technician contact details stay masked |

**About 60 s of latency is not the constraint.** Failures develop over hours. The decision window is the JIS buffer and the next planned break, not the second.

---

## Value model, layer 1: Volta's own P&L (illustrative)

These are assumptions for Volta's finance team to replace with actuals in the pilot. The per-event savings come from the maintenance history.

| Input | Value | Source |
|---|---|---|
| Stations | 96 (3 plants, 12 lines) | Volta fleet in the demo |
| Unplanned failures per station per year | 2 | **Assumption** (Volta to confirm) |
| Share of failures converted to planned repairs | 70% | **Assumption**, below the 100% detection rate, to allow for crew availability |
| Internal line downtime cost | $15,000 per hour | **Assumption** (Volta to confirm) |
| Downtime and parts saved per converted failure | 85 min, $6,300 | Maintenance history |

| Result per year | Value |
|---|---|
| Failures converted to planned repairs | 134 of 192 |
| Line downtime avoided | **about 190 hours** (about +0.26 OEE availability points) |
| Downtime cost avoided | about $2.8M |
| Parts cost avoided | about $0.85M |
| False alarm cost (5% of alerts, each about a planned inspection) | about -$0.06M |
| **Net internal value** | **about $3.6M** |

---

## Value model, layer 2: OEM line-stop charges avoided (illustrative)

Most unplanned failures are absorbed by bank stock, overtime or expedited parts. Only some outlast the buffer and reach the OEM. That share is the key input.

| Share of unplanned failures that stop the OEM line | OEM stops per year (192 failures) | Charges avoided at 70% conversion |
|---|---|---|
| 2% | about 4 | **about $1.6M** |
| 5% (base case) | about 10 | **about $4.0M** |
| 10% | about 19 | **about $8.0M** |

- Charge per OEM stop: about $595,000 on average. That is about 44 minutes beyond the buffer at Volta's synthetic contract rate per line.
- **Not monetized, but decisive:** a clean delivery scorecard with each OEM. In this niche, the scorecard decides who gets the next vehicle program.
- Layer 1 sensitivity at 70% conversion: $1.8M at $5k/h internal downtime cost, $3.6M at $15k/h, $10.2M at $50k/h.

---

## For Ingrid Solberg, COO: what this moves on her scorecard

A Tier-1 COO is typically judged by the CEO and the board on a short list. Volta to confirm in discovery.

| How Ingrid is judged | What moves | Measured or modeled |
|---|---|---|
| **EBITDA margin** after annual OEM price-downs | Lower downtime and parts cost, without more headcount | About $3.6M per year (layer 1) |
| **OEM charges and premium freight** | Fewer failures outlast the JIS buffer | About $4.0M per year in the base case (layer 2) |
| **OEM supplier scorecard** (delivery, quality) and **next program awards** | Fewer OEM line stops and fewer weld or seal quality escapes | Exposure per OEM, live, in Genie |
| **Capex and free cash flow** | More output from the same 12 lines | About +0.26 OEE availability points, no new equipment |
| **Rollout risk across plants** | One governed platform, plant by plant | Each plant sees only its own data |

**What we need from Ingrid:** sponsor a 90-day pilot on one Plant East line supplying Aurora Elbil. Name Henrik as owner, and agree the KPIs on the pilot slide as the yardstick.

---

## For Henrik Lindqvist: what moves in his monthly operations review

Henrik reports these every month. They usually set his bonus too, through plant OEE and the maintenance budget.

| Henrik's KPI | Today (history) | With 70% of failures converted |
|---|---|---|
| **Planned maintenance share** | 20% of repairs | **about 76%** |
| **Mean repair time per maintenance event** | 96 min | **about 48 min** |
| **Maintenance parts spend** (same history) | $8.1M | **about $3.3M** (-60%) |
| **Unplanned downtime hours** | baseline | **about -190 h per year** across the fleet |
| **Alert precision** (crew trust) | no alerts | **95%** |
| **Warning lead time** | none | **median about 4 operating hours** |

**How his team's day changes:**
- **Bjørn:** his plant screen ranks stations by risk and names the top signal and the process step at stake. He schedules the repair inside the next planned break.
- **Sigrid:** she gets one-click work orders that say what is wrong and where to look.
- **Henrik:** he asks Genie: "Which failure mode costs us the most downtime?" or "Which lines supplying Nordvik Motors have the least buffer?"
- **Henrik's engineers:** they run what-if checks, such as "if the welder's bearing temperature drops 10%, what is the risk?" Answers come back in under 150 ms.

---

## How it works (one platform, no glue)

```
Station sensors ──► Zerobus streaming ingest ──► Clean + score in-stream ──► Live plant screen
                    (no Kafka to run)              (failure model, every 10 s)     (Databricks App)
                                                          │                          │ work orders
                                                          ▼                          ▼
                   OEM programs + JIS terms ──► Unity Catalog: governed KPIs ◄── Lakebase (operational DB)
                                                          │
                                                          ▼
                                    Genie agent: risk, exposure, MTTR in plain language
```

| Piece | Business role at Volta |
|---|---|
| Lakeflow Connect Zerobus | Plant gateways push data directly into governed tables |
| Spark Declarative Pipelines | Data-quality rules drop bad readings. Scoring runs continuously |
| ML model in Unity Catalog | One versioned model for streaming scores and engineer what-ifs |
| Unity Catalog reference data | OEM program, JIS buffer and line-stop terms per line, so risk is expressed in dollars per OEM |
| Lakebase | Millisecond reads for the screen and transactional work orders |
| Genie agent | Self-service answers for Ingrid, Henrik and Astrid on certified KPIs |
| Databricks App | The front end for Bjørn, Sigrid and the other supervisors and technicians |

---

## Why Volta's operations team can trust it

- **Data quality is enforced, not hoped for.** Pipeline expectations drop invalid sensor readings and count them visibly.
- **Explainable alerts.** Each alert names the sensor and the process step. Crews know where to look.
- **Access by plant.** Each plant's team sees only its own plant. This was proven on the app's own identity, not on an admin account. Technician contact details are masked.
- **One definition of each KPI.** Genie, dashboards and the app use the same governed metric definitions and the same contract terms. There is no spreadsheet drift before the OEM review.
- **Auditable.** Lineage from sensor to screen, model versions, work-order history and every model call are tracked. This supports the traceability that automotive quality audits ask for.
- **Validated before release.** Genie passed a 12-question benchmark against reference SQL before any user touched it.

---

## Pilot plan: 90 days on one Plant East line, measured in Volta's KPIs

| Phase | Weeks | Deliverable |
|---|---|---|
| Baseline | 1 to 2 | Line PLT-E-A (Aurora Elbil A3 Hatch). Capture 12 months of failures, MTTR, downtime cost, PM schedule, OEM charges and scorecard |
| Connect | 3 to 5 | Stream the line's sensors through Zerobus. Load the maintenance history from Volta's CMMS and the JIS terms from the OEM contract |
| Model | 6 to 8 | Train on Volta's failure history. Agree the alert threshold with Henrik |
| Operate | 9 to 12 | Bjørn's crew runs alerts in shadow mode, then live. Work orders flow back to the CMMS |

**Success criteria, agreed up front:**
- At least 70% of failures flagged with more warning than the line's JIS buffer (60 min)
- Alert precision of at least 80%
- Zero OEM line stops caused by a station on the pilot line that the model flagged in time
- Measured reduction in unplanned downtime hours and a rise in planned maintenance share against the baseline
- A business case for all 12 lines and three OEMs, built from pilot data rather than assumptions

---

## What we are honest about

- **The demo uses synthetic data.** Volta's real failure signatures will be noisier. That is why the pilot retrains on Volta's history.
- **The OEMs, programs and contract terms are fictional.** The line-stop charges are shaped like automotive supply terms. They are not quotes from a real contract.
- **The value model is illustrative.** Failure frequency, downtime cost and the share of failures that reach the OEM are Volta's inputs, not ours.
- **About 60 s from sensor to screen.** That is right for failures that develop over hours. It is not a safety interlock and does not replace machine protection.
- **Recovery shows about 3 minutes after a repair**, while the model's window refills with healthy data.
- **Alert explanations are simple.** They name the sensor that deviates most, not a full root-cause analysis. Weld and seal quality checks stay in Volta's quality system.
- **Data access applies at the app level today.** Per-user filtering for each viewer is a pilot add-on.

---

## The ask

1. **Ingrid Solberg:** approve a 90-day pilot on line PLT-E-A and confirm Henrik as maintenance owner.
2. **Henrik Lindqvist:** share 12 months of failure and work-order history and the current PM schedule.
3. **Astrid Nygård:** share the line's JIS terms and the last 12 months of Aurora Elbil scorecard and charges.
4. **Together:** agree the baseline and the success criteria before day 1.

**The outcome we commit to measure:** no OEM line stops from flagged stations, fewer unplanned stops, shorter repairs and lower parts spend. The result is a business case for all of Volta Industrial, built from its own data, that Ingrid can bring to the board and to the next OEM sourcing decision.

---

## Appendix: where the numbers come from

All figures are from executed runs, committed as text in this repo. How the industry review gaps were closed: `docs/INDUSTRY_FIT.md`.

| Claim | Evidence |
|---|---|
| 271/271 failures flagged, median 244 s lead (about 4 operating hours), PR-AUC 0.91, precision 0.95 | `evidence/04_training/02_train_model.md` |
| 112 vs 28 min downtime, $7,200 vs $870 parts, 1,096 corrective vs 268 preventive repairs | `evidence/03_backfill/01_backfill_history.md` (maintenance log summary) |
| OEM programs, JIS buffers, line-stop charges, process steps, exposure per line and per OEM, $595k average charge per failure | `evidence/11_industry_context/05_industry_context.md` |
| Henrik's KPIs (planned share, mean repair time, parts spend), layer 1 and layer 2 value, OEE points, both sensitivity tables | `evidence/11_industry_context/05_industry_context.md`, sections "Scorecard KPIs", "Value model", "Sensitivity" |
| Live run on PLT-E-A03 (overheating): fault, HIGH, work order, repair, NORMAL | `evidence/08_app/e2e_fault_injection.md`, `evidence/10_evidence_notebooks/E08_end_to_end.md` |
| 3.9 s to clean data, about 60 s to the screen | `evidence/06_live_pipeline/04_live_evidence.md`, `evidence/08_app/` |
| 4 to 32 ms app reads, 12 to 14 ms work order round trips | `evidence/08_app/e2e_fault_injection.md`, `evidence/10_evidence_notebooks/E04_lakebase.md` |
| Genie 12/12, including OEM exposure questions | `evidence/07_genie/benchmark.md`, `evidence/10_evidence_notebooks/E06_genie.md` |
| Plant-level access on the app identity (6 → 12 → 6 rows) | `evidence/08_app/governance_as_app_sp.json`, `evidence/10_evidence_notebooks/E05_governance.md` |

**Layer 1 arithmetic:** 96 × 2 = 192 failures. 70% = 134 converted. 134 × 84.6 min = 189 h × $15k = $2.83M. 134 × $6,329 = $0.85M. False alarms: 134 / 0.95 − 134 ≈ 7, at about $7.9k each = $0.06M. Net = $3.62M.

**Layer 2 arithmetic:** 192 failures × 5% reaching the OEM = 9.6 stops. × 70% avoided × $594,853 = $4.0M.

**Henrik's KPIs:** 70% of the 1,096 failures are converted. Corrective repairs fall to 329 and preventive repairs rise to 1,035. Planned share = 1,035 / 1,364 = 76%. Mean repair time = (329 × 112.3 + 1,035 × 27.7) / 1,364 = 48 min. Parts spend = 329 × $7,200 + 1,035 × $871 = $3.27M, down from $8.12M.

Volta Industrial, Nordvik Motors, Fjord Electric, Aurora Elbil and all personas are fictional, and so is all of the data.
