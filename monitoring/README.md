# Monitoring

Observability configs for AI Engine.

## Prometheus alerts

Load `prometheus-alerts.yml` into Prometheus:

```yaml
# prometheus.yml
rule_files:
  - /path/to/AI_engine/monitoring/prometheus-alerts.yml
```

Alerts cover circuit breakers, high error rate, latency, cache hit rate, and provider downtime.

## Grafana dashboard

Import `grafana/provider-health-dashboard.json` via Grafana UI:

1. Dashboards → Import
2. Upload the JSON file
3. Select your Prometheus datasource

Panels: healthy providers, open circuit breakers, cache hit rate, p95 latency,
RPS by provider, success rate, latency percentiles, circuit failures, cache size, errors, active alerts.

## Metric names expected

- `ai_engine_request_duration_seconds_*`
- `ai_engine_circuit_breaker_state`
- `ai_engine_circuit_breaker_failures_total`
- `ai_engine_cache_hits_total` / `ai_engine_cache_requests_total`
- `ai_engine_cache_size` / `ai_engine_cache_memory_bytes`
- `ai_engine_errors_total`
