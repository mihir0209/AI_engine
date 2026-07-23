# Kubernetes deployment samples

```bash
# Build image (example)
docker build -t ai-engine:latest .

# Apply manifests
kubectl apply -f deploy/k8s/deployment.yaml

# Optional secrets
kubectl create secret generic ai-engine-secrets \
  --from-literal=redis-url=redis://redis:6379/0
```

Prometheus: point scrapes at Service `:8000/metrics` if enabled.
Grafana: import `monitoring/grafana/provider-health-dashboard.json`.
