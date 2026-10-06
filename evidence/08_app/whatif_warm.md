# Warm Model Serving what-if calls through the app

The first call in e2e_fault_injection.md (62 s) hit a scale-to-zero cold start. These follow-up calls are warm.

```json
{"station_id":"PLT-E-A03","sensor":"bearing_temp_c","change_pct":25.0,"current_probability":0.0114,"scenario_probability":0.1602,"serving_latency_ms":139.5,"endpoint":"pdm-station-risk"}
{"station_id":"PLT-E-A03","sensor":"bearing_temp_c","change_pct":25.0,"current_probability":0.0114,"scenario_probability":0.1602,"serving_latency_ms":92.4,"endpoint":"pdm-station-risk"}
{"station_id":"PLT-E-A03","sensor":"bearing_temp_c","change_pct":25.0,"current_probability":0.0114,"scenario_probability":0.1602,"serving_latency_ms":41.4,"endpoint":"pdm-station-risk"}
```
