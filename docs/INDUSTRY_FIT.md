# Industry fit: review gaps and how they were closed

The build passed. The industry review named two gaps. This page lists each gap, what changed, and the executed evidence for it. All companies, people and contract terms are fictional, and all data is synthetic.

## Gap 1: no named niche

> "The sub-vertical is described through generic station types (CNC mill, press, welder, conveyor, robot arm) rather than a named manufacturing niche with its own competitive pressures, so the market-differentiation angle stays general rather than tied to a specific segment of manufacturing."

**The niche.** Volta Industrial is a Tier-1 automotive supplier. It builds aluminum EV battery enclosures (trays, covers, cooling plates) for three OEMs: Nordvik Motors, Fjord Electric and Aurora Elbil. It ships them just-in-sequence (JIS) from 12 lines.

**Competitive pressures:**
- JIS buffers of 45 to 90 minutes
- per-minute OEM line-stop charges
- annual price-downs
- OEM scorecards that decide the next program award
- safety-critical weld and sealing quality

**What changed:**

| Change | Where | Executed evidence |
|---|---|---|
| Each line is mapped to its OEM, vehicle program, part family, JIS buffer and contract line-stop charge | `pdm_raw.line_programs`, built by `src/notebooks/05_industry_context.py` | `evidence/11_industry_context/05_industry_context.md`, section "OEM programs per line" (12 rows) |
| The generic station types are mapped to battery enclosure process steps and critical quality characteristics, such as friction-stir welding for weld seam integrity and sealant dispensing for IP67 sealing | `pdm_raw.process_steps` | same file, section "Enclosure process step per station position" (8 rows) |
| Live risk is expressed as OEM delivery exposure: minutes beyond the JIS buffer, the contract charge, and the charge weighted by risk, per line and per OEM | view `pdm_ops.oem_delivery_exposure` | same file, sections "Exposure right now" (12 lines) and "Exposure per OEM customer" |
| Average contract charge per unplanned failure: 112 min of downtime against a 43.5 min average buffer gives about $595k | same view logic, using the fleet average | same file, section "Contract exposure of one unplanned failure" |
| Genie answers in the niche's terms: OEM, program, JIS buffer, exposure | `src/genie/space_config.py` (source, instructions, example SQL, 2 benchmark questions) | `evidence/07_genie/benchmark.md` (12/12), `evidence/10_evidence_notebooks/E06_genie.md` (12/12, live re-run), `evidence/09_deployed_resources/genie_space.json` (deployed config includes `oem_delivery_exposure`) |
| The deck leads with the niche, using a market slide, a process map, an OEM exposure slide and a corrected live-run story (welder PLT-E-A03 on the Aurora Elbil line) | `presentation/deck.md` | appendix of the deck, linked to the files above |

## Gap 2: KPIs not tied to how leaders are judged

> "The executive framing names the KPIs each leader owns but stops short of tying them to how those leaders are actually compensated or judged by their own board or operations review."

**What changed:**

| Change | Where | Executed evidence |
|---|---|---|
| The COO slide maps a typical Tier-1 board scorecard to the levers this solution moves, with numbers. The scorecard covers EBITDA under price-downs, OEM charges and premium freight, the OEM scorecard and next program awards, capex and free cash flow, and rollout risk | `presentation/deck.md`, "For Ingrid Solberg, COO" | Layer 1 and layer 2 values below |
| The Head of Maintenance slide maps the KPIs of his monthly operations review, which usually also set his bonus through plant OEE and the maintenance budget, to before and after values | `presentation/deck.md`, "For Henrik Lindqvist" | `05_industry_context.md`, section "Henrik Lindqvist ... operations review KPIs": planned share 19.6% → 75.9%, mean repair time 95.7 → 48.1 min, parts spend $8.12M → $3.27M |
| The value model has two layers. Layer 1 is Volta's own P&L. Layer 2 is OEM line-stop charges avoided | `presentation/deck.md`, value slides | `05_industry_context.md`, section "Value model": layer 1 $3.64M, layer 2 $4.00M, +0.26 OEE availability points |
| Sensitivity for both layers | same | `05_industry_context.md`, section "Sensitivity": layer 1 $1.3M to $13.1M, layer 2 $1.6M to $8.0M |

**Measured vs. assumed:**
- **Measured:** repair counts, downtime and parts cost come from the synthetic maintenance history. Alert precision (0.95) comes from model training (`evidence/04_training/02_train_model.md`).
- **Assumed:** failures per station per year, conversion share, downtime cost, the share of failures that reach the OEM, and operating hours. These are notebook widgets, so finance can re-run the notebook with actuals.
- **Typical, not measured:** the compensation and scorecard framing describes typical Tier-1 practice. The deck marks it "Volta to confirm in discovery".

## Not changed

- **The live app screen does not show OEM exposure yet.** Genie and SQL do. Adding it means restarting Lakebase, the pipelines and the app, and re-running the app evidence.
- **The raw data keeps the generic station type values** (`cnc_mill`, `welder` and so on). The process step is joined through `pdm_raw.process_steps`, so the model, the pipeline and their evidence stay unchanged and valid.
