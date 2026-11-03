---
marp: true
theme: volta
title: Volta Industrial. Never stop the OEM line. Live predictive maintenance for EV battery enclosures on Databricks
paginate: true
---

<!-- _class: title -->

# Volta Industrial: never be the supplier that stops the OEM line

**Live predictive maintenance for aluminum EV battery enclosure lines, on one Databricks platform**

Volta Industrial is a Tier-1 automotive supplier. It builds battery trays, covers and cooling plates for three EV makers: Nordvik Motors, Fjord Electric and Aurora Elbil. It ships them just-in-sequence from 12 lines in three plants.

Prepared for **Ingrid Solberg** (COO, executive sponsor) and **Linnea Berg** (Lead App Developer, Volta Digital Manufacturing, who would own and run the app). The app is built for **Bjørn Halvorsen**, Maintenance Supervisor in Plant East.

All companies, people and data are fictional and synthetic. No real customer data was used.

*About 20 minutes: 2 setup, 3 problem, 8 demo, 3 value, 4 questions and the ask.*

---

<!-- _class: dense -->

## Who is in the room

| | **Ingrid Solberg**, COO | **Linnea Berg**, Lead App Developer |
|---|---|---|
| Decides | Funds the program and the rollout to all plants | Whether her team can own, extend and run the app in production |
| Judged on | EBITDA margin under OEM price-downs, OEM charges, the OEM scorecard that decides the next program award, capex | Uptime and response time of the plant apps, release speed, security reviews passed, on-call load |
| Wants to hear | What it is worth, how fast, what the risk is | How it is built, how data and auth work, how it is tested and deployed, what breaks |

The app's user is **Bjørn Halvorsen**, Maintenance Supervisor in Plant East. He is not in the room, but every screen in the demo is his.

---

<!-- _class: dense -->

## The outcome in one slide

**Every failure in the test set was flagged before it happened, with a median of about 4 operating hours of warning. Volta's JIS buffers are only 45 to 90 minutes.**

| | What we showed | For Ingrid | For Bjørn, the app's user |
|---|---|---|---|
| Failures caught early | **271 of 271** on a held-out time window | No OEM line stop from a flagged station | Repairs get planned, not rushed |
| Warning | **About 4 operating hours** (median) | The OEM never notices | Fix it in the next planned break |
| Alert precision | **95%** at HIGH | Few wasted inspections | His crew can trust the alerts. About 1 in 20 is a false alarm |
| Planned repairs | **20% today → about 76%** | Lower downtime and parts cost | Fewer emergency call-outs |
| Repair minutes per event | **96 → about 48** | More output from the same lines | Half the time per job |
| Value (illustrative) | **About $3.6M + $4.0M a year** | Own P&L + OEM charges avoided | |

In the live run, the at-risk welder was **repaired and never failed**.

---

<!-- _class: dense -->

## The problem, in Volta's numbers

From Volta's synthetic maintenance history (96 stations, 1,096 failures):

| | Downtime | Parts |
|---|---|---|
| Repair after a failure | **112 min** | **$7,200** |
| Planned repair | **28 min** | **$870** |

- **Only 20% of repairs are planned today.** The rest happen after the station has failed.
- **112 minutes is longer than every JIS buffer** (45 to 90 min). An unplanned failure stops the OEM's line for **about 44 minutes**, which costs **about $595,000** under Volta's contracts.
- **A 28-minute planned repair fits inside every buffer.** The OEM never sees it.
- **And in this niche, the OEM scorecard decides the next vehicle program.** One line stop is a mark against Volta.

**Turning a failure into a planned repair turns an OEM line stop into a non-event.**

---

<!-- _class: dense -->

## Live: Bjørn's shift on the Aurora Elbil line

Station **PLT-E-A03**, the frame welder on line PLT-E-A in Plant East. The line builds battery trays for the Aurora Elbil A3 Hatch, with a 60-minute JIS buffer. 1 demo minute ≈ 1 operating hour.

| | Tell | Show | What it means |
|---|---|---|---|
| **1 · The alert** | "What Bjørn sees on his screen" | The welder starts to overheat. Its risk climbs from 1% to HIGH (79%, then 99%). Top signal: motor current, 10% above normal | Hours of warning against a 60-minute buffer. 95% of these alerts are real |
| **2 · Act and recover** | "Now the part that pays" | One click creates a P1 work order, stored in about 12 ms. The technician completes it and the risk returns to NORMAL | A 28-minute planned job instead of 112 minutes. No Aurora Elbil line stop, which would have cost about **$575,000** |
| **3 · Ingrid's question** | "The question before an OEM review" | Genie: "Which OEM programs are exposed to a line stop right now?" It ranks the lines by risk-weighted exposure | Ingrid knows her exposure per OEM. Bjørn knows where to send the crew first |

---

<!-- _class: dense -->

## Ingrid's view: OEM delivery exposure, live

One governed view joins live risk to each line's OEM contract: "If the riskiest station on this line fails now, does the OEM line stop, and what does it cost?"

Snapshot from the running system (Genie's answer, reproduced in SQL):

| Line | OEM program | Riskiest station | Risk | OEM stop if it fails | Risk-weighted exposure |
|---|---|---|---|---|---|
| PLT-S-B | Fjord Electric FE Pace Sedan | Stamping press | HIGH, 99.7% | 51 min | **$913k** |
| PLT-N-C | Nordvik Motors NV-e5 Crossover | Stamping press | HIGH, 99.9% | 51 min | **$609k** |
| PLT-E-A | Aurora Elbil A3 Hatch | Extrusion CNC | ELEVATED, 48% | 55 min | **$294k** |

- **Per OEM:** Fjord Electric $1.09M, Nordvik Motors $0.80M, Aurora Elbil $0.46M.
- **Tested before anyone used it:** Genie answered 12 of 12 benchmark questions correctly, against reference SQL.

---

<!-- _class: dense -->

## For Ingrid: what it is worth, and what moves on her scorecard

Illustrative for the 96-station fleet. Assumptions: 2 unplanned failures per station per year, 70% converted into planned repairs, $15,000 per hour of internal line downtime. Volta's finance team replaces these with actuals in the pilot.

| Layer | What it is | Per year |
|---|---|---|
| **1 · Own P&L** | About 190 hours of line downtime avoided, plus parts, minus false-alarm inspections | **about $3.6M** (+0.26 OEE availability points) |
| **2 · OEM charges** | If 5% of unplanned failures reach the OEM: about 10 stops × $595k, 70% avoided | **about $4.0M** (2%: $1.6M; 10%: $8.0M) |
| **3 · Next program award** | A clean delivery scorecard with each OEM | not monetized, decisive |

| How Ingrid is judged (typical Tier-1, Volta to confirm) | What moves |
|---|---|
| EBITDA margin after annual OEM price-downs | Layer 1, without more headcount |
| OEM charges and premium freight | Layer 2 |
| OEM scorecard and next program award | Fewer line stops, exposure per OEM visible live |
| Capex and free cash flow | More output from the same 12 lines, no new equipment |

---

<!-- _class: dense -->

## For Bjørn, the app's user: how his shift changes

**Today**
- He finds out about a failure when the line stops, and the JIS clock is already running.
- Preventive maintenance follows a calendar, so some stations get serviced too early and others too late.
- Four out of five repairs are emergencies.

**With the app**
- **Which station:** the plant screen ranks all stations by failure risk and refreshes every few seconds.
- **Why:** each alert names the top signal, for example motor current 10% above normal, so the technician knows where to look.
- **How much time:** hours of warning, so he schedules the repair into the next planned break.
- **One click:** a work order for the technician, stored transactionally. In the pilot it also flows into the CMMS, so nothing is typed twice.
- **Proof it worked:** after the repair, the station's risk returns to NORMAL on the same screen.

| Bjørn's numbers | Today | With 70% of failures caught |
|---|---|---|
| Planned share of repairs | 20% | **about 76%** |
| Repair minutes per event | 96 | **about 48** |
| Alerts he can trust | none | **95% precision** |
| Warning before a failure | none | **about 4 operating hours** |

---

<!-- _class: dense -->

## For Linnea: how the app is built, and what her team would own

```
Station sensors ──► Zerobus ──► SDP pipeline: clean + score every 10 s (UC model) ──► Delta
                                                                        │ synced table, about 4 s
Bjørn's browser ◄── FastAPI on Databricks Apps ◄── Lakebase (Postgres) ◄┘
   (polls 2 s)        │  writes work orders ──► Lakebase ──► Lakehouse Sync ──► Unity Catalog
                      ├─► Model Serving via AI Gateway (what-if)
                      └─► Genie Conversation API (plain-language questions)
```

| Concern | How it works today | Measured |
|---|---|---|
| **Data quality** | Pipeline expectations drop invalid readings and count them. A window with too few readings is not scored | 3.9 s sensor to clean data, about 60 s to screen |
| **Reads** | The live risk state is a Lakebase synced table: read-only Postgres, primary key (station, window) | 4 to 32 ms per query |
| **Writes** | Work orders and commands are transactional Postgres rows. Lakehouse Sync streams the changes back to UC | 12 to 14 ms round trip |
| **Identity** | The app's own service principal. Credentials are injected by the platform; Postgres OAuth tokens are minted and refreshed in the connection pool | no secrets in code |
| **Access** | Least-privilege grants on the app identity. A plant-level row filter, proven on that identity | 6 → 12 → 6 rows |
| **Model calls** | What-if goes through AI Gateway, with every call tracked | 41 to 140 ms warm |
| **Deploy** | App, pipeline, endpoint and jobs are one bundle in Git. The deployed code is verified against the repo by checksum | one command per environment |
| **Test** | A scripted end-to-end run drives every API call through the deployed app, with timings | fault → HIGH → work order → NORMAL |

---

<!-- _class: dense -->

## Pilot and the ask

**90 days on line PLT-E-A (Aurora Elbil A3 Hatch, Plant East), with Bjørn's crew**

| Weeks | What happens |
|---|---|
| 1 to 2 | Baseline: 12 months of failures, repair times, downtime cost, OEM charges |
| 3 to 5 | Connect the line's sensors through Zerobus. Load the CMMS history and the JIS terms |
| 6 to 8 | Train on Volta's history. Set the alert threshold with Bjørn |
| 9 to 12 | Bjørn's crew runs the alerts in shadow mode, then live |

**Success, agreed up front:** at least 70% of failures flagged with more than 60 minutes of warning; at least 80% alert precision; zero OEM stops from flagged stations; a measured drop in unplanned downtime.

**The ask**
1. **Ingrid:** sponsor the 90-day pilot on PLT-E-A.
2. **Linnea:** her team co-owns the app from week 1: code, deployment and on-call, with us alongside. Bjørn's crew runs the alerts and sets the threshold with us.
3. **Together:** agree the baseline and the success criteria before day 1.

**What we are honest about:** the demo uses synthetic data and fictional contracts, so the value model is illustrative until the pilot. About 60 s to screen is right for this decision, but it is not a safety interlock. Alerts name the most deviating sensor, not a full root cause. For Linnea: Genie runs as the app identity, so per-viewer filtering needs on-behalf-of-user auth; the model endpoint scales to zero and its first call after idle took about 60 s; a few settings in the app config are still hard-coded instead of bundle variables.

---

<!-- _class: tiny -->

## Appendix: where the numbers come from

Not presented. For questions. All figures are from executed runs, committed as text in this repo. How the industry review gaps were closed: `docs/INDUSTRY_FIT.md`.

| Claim | Evidence |
|---|---|
| 271/271 failures flagged, median 244 s lead (about 4 operating hours), PR-AUC 0.91, precision 0.95 | `evidence/04_training/02_train_model.md` |
| 112 vs 28 min downtime, $7,200 vs $870 parts, 1,096 corrective vs 268 preventive repairs | `evidence/03_backfill/01_backfill_history.md` |
| OEM programs, JIS buffers, line-stop charges, exposure per line and per OEM, $595k average charge per failure | `evidence/11_industry_context/05_industry_context.md` |
| Planned share, repair minutes, parts spend, layer 1 and layer 2 value, OEE points, sensitivity | `evidence/11_industry_context/05_industry_context.md`, sections "Scorecard KPIs", "Value model", "Sensitivity" |
| Live run on PLT-E-A03 (overheating): fault, HIGH, work order, repair, NORMAL | `evidence/08_app/e2e_fault_injection.md`, `evidence/10_evidence_notebooks/E08_end_to_end.md` |
| 3.9 s to clean data, about 60 s to the screen, 12 ms work orders | `evidence/06_live_pipeline/04_live_evidence.md`, `evidence/08_app/`, `evidence/10_evidence_notebooks/E04_lakebase.md` |
| Genie 12/12, including OEM exposure questions | `evidence/07_genie/benchmark.md`, `evidence/10_evidence_notebooks/E06_genie.md` |
| Plant-level access on the app identity (6 → 12 → 6 rows) | `evidence/08_app/governance_as_app_sp.json`, `evidence/10_evidence_notebooks/E05_governance.md` |

**Layer 1:** 96 × 2 = 192 failures. 70% = 134 converted. 134 × 84.6 min = 189 h × $15k = $2.83M. 134 × $6,329 = $0.85M. False alarms ≈ 7 × $7.9k = $0.06M. Net = $3.62M.

**Layer 2:** 192 × 5% = 9.6 OEM stops. × 70% × $594,853 = $4.0M.

**Maintenance KPIs:** 70% of 1,096 failures converted: 329 corrective, 1,035 planned. Planned share = 1,035 / 1,364 = 76%. Repair minutes = (329 × 112.3 + 1,035 × 27.7) / 1,364 = 48. Parts = $8.12M → $3.27M.

Volta Industrial, Nordvik Motors, Fjord Electric, Aurora Elbil and all personas are fictional, and so is all of the data.
