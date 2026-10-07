# Model Serving what-if calls through the AI Gateway

The app (`POST /api/whatif`, running as its service principal) posts to the endpoint's AI Gateway URL. Usage tracking is on, so each call also lands in `system.serving.endpoint_usage` (see E03 §5). Captured 2026-10-07T23:23:44Z, station PLT-E-A01.

```json
{"station_id":"PLT-E-A01","sensor":"vibration_rms","change_pct":10.0,"current_probability":0.0767,"scenario_probability":0.1222,"serving_latency_ms":132.1,"endpoint":"pdm-station-risk","gateway_url":"https://fevm-serverless-stable-am1uc2.cloud.databricks.com/serving-endpoints/pdm-station-risk/invocations"}
{"station_id":"PLT-E-A01","sensor":"vibration_rms","change_pct":25.0,"current_probability":0.0524,"scenario_probability":0.2921,"serving_latency_ms":101.8,"endpoint":"pdm-station-risk","gateway_url":"https://fevm-serverless-stable-am1uc2.cloud.databricks.com/serving-endpoints/pdm-station-risk/invocations"}
{"station_id":"PLT-E-A01","sensor":"vibration_rms","change_pct":50.0,"current_probability":0.0524,"scenario_probability":0.868,"serving_latency_ms":128.0,"endpoint":"pdm-station-risk","gateway_url":"https://fevm-serverless-stable-am1uc2.cloud.databricks.com/serving-endpoints/pdm-station-risk/invocations"}
```
