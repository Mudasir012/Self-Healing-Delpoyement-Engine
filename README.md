# Self-Healing Deployment Engine

An event-driven, automated remediation system for Kubernetes. Ingests Prometheus Alertmanager webhooks, classifies failures, matches them against configurable rules, and executes automated recovery actions — with optional human-in-the-loop approval via Slack.

## Architecture

```
Prometheus ──(alerts)──> Alertmanager ──(webhook)──> Engine API ──> Classifier ──> Rule Engine ──> Audit Log ──> Celery Worker ──> K8s/Argo Actions
                                                          │                                                    │
                                                          ├── Slack (approval request) ──────> Operator ──> approve/reject ──>│
                                                          └── Prometheus metrics ──> Grafana                              │
                                                                                                                          └── Slack (result notification)
```

## Features

- **Automatic alert ingestion** from Prometheus Alertmanager via webhook
- **Smart classification** using regex patterns on alert labels and annotations
- **Rule-driven remediation** with configurable YAML rules (action, cooldown, approval gate)
- **Cooldown mechanism** prevents repeated actions on the same target within a configurable window
- **Human-in-the-loop approvals** for sensitive actions (scaling, rollbacks) via Slack interactive messages or REST endpoints
- **Kubernetes actions**: pod restart, pod deletion, deployment scaling (up/down)
- **GitOps integration**: Argo CD rollback for bad deployments
- **Infrastructure actions**: disk cleanup (evict agent pods on full node), log rotation via exec
- **Rich notifications** via Slack (approval requests, success/failure alerts)
- **Full observability**: Prometheus metrics, Loki log aggregation, Jaeger distributed tracing, Grafana dashboard
- **Comprehensive audit trail** with every action logged to PostgreSQL

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI (Python 3.12) |
| Async Server | Uvicorn |
| Task Queue | Celery with Redis broker/backend |
| Database | PostgreSQL 16 via SQLAlchemy 2.0 + Alembic |
| Validation | Pydantic v2 |
| Kubernetes | Official `kubernetes` Python client |
| GitOps | Argo CD HTTP API (via httpx) |
| Notifications | Slack SDK |
| Monitoring | Prometheus, Alertmanager, Grafana |
| Logging / Tracing | structlog, Loki, Jaeger |
| Testing | pytest, pytest-cov, unittest.mock |

## Quick Start (Local Dev)

```bash
# Start dependencies (postgres, redis) and run the API with hot-reload:
make dev

# Or start the full stack (all services):
docker-compose up -d

# Run database migrations:
make migrate

# Run tests:
make test

# Run linting:
make lint
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://remediator:remediator@localhost:5432/self_healing` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery |
| `SLACK_BOT_TOKEN` | `""` | Slack bot token (notifications disabled if empty) |
| `SLACK_CHANNEL` | `#remediation` | Slack channel for notifications |
| `K8S_IN_CLUSTER` | `false` | Use in-cluster K8s config or kubeconfig file |
| `LOG_LEVEL` | `INFO` | Logging level |
| `APPROVAL_TIMEOUT_SECONDS` | `300` | Time before a pending approval times out |
| `ARGO_SERVER` | `argocd-server.argocd.svc.cluster.local` | Argo CD server address |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/webhook/alertmanager` | Alertmanager webhook ingestion |
| POST | `/webhook/slack/actions` | Slack interactive message callback |
| POST | `/approve/{audit_id}` | Approve a pending remediation action |
| POST | `/reject/{audit_id}` | Reject a pending remediation action |
| GET | `/audit` | List audit logs (with pagination, filtering) |
| GET | `/audit/{audit_id}` | Get a single audit log entry |

## Rules

Default remediation rules are defined in `engine/rules.yaml`:

```yaml
rules:
  - condition: crash_loop
    action: restart_pod
    cooldown: 300
    approval_required: false

  - condition: high_memory
    action: scale_up
    params:
      replicas_increase: 2
    cooldown: 600
    approval_required: true

  - condition: bad_deployment
    action: rollback
    cooldown: 0
    approval_required: true

  - condition: disk_full
    action: disk_cleanup
    cooldown: 3600
    approval_required: false
```

## Sending Test Alerts

```bash
curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "self-healing-engine",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "CrashLoopBackOff",
        "severity": "critical",
        "failure_type": "crash_loop",
        "app": "api-gateway",
        "namespace": "production",
        "pod": "api-gateway-7d8f9"
      },
      "annotations": {
        "summary": "CrashLoopBackOff",
        "description": "Pod api-gateway-7d8f9 in production is in CrashLoopBackOff"
      },
      "startsAt": "2024-01-01T00:00:00Z",
      "fingerprint": "abc123"
    }]
  }'
```

## Kubernetes Deployment

```bash
make k8s-deploy
```

Applies the Kustomize manifests in `infra/k8s/`, which include namespaces, PostgreSQL StatefulSet, Redis, engine API and Celery worker deployments, RBAC, and ingress.

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start postgres + redis, run API with hot-reload |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage |
| `make lint` | Run ruff linter |
| `make build` | Build Docker images |
| `make up` | Start all services via docker-compose |
| `make down` | Stop all services |
| `make logs` | Tail docker-compose logs |
| `make clean` | Remove volumes and caches |
| `make migrate` | Run Alembic database migrations |
| `make k8s-deploy` | Deploy to Kubernetes |
| `make k8s-delete` | Remove from Kubernetes |
