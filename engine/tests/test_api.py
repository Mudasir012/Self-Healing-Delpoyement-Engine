from fastapi.testclient import TestClient
import pytest
import uuid
import os

from app.main import app
from app.database import get_db
from app.config import settings

client = TestClient(app)

INTEGRATION_TESTS = os.environ.get("SELF_HEALING_INTEGRATION", "").lower() in ("1", "true", "yes")


def _db_is_reachable() -> bool:
    try:
        from sqlalchemy import create_engine
        eng = create_engine(settings.database_url, connect_timeout=3)
        conn = eng.connect()
        conn.close()
        eng.dispose()
        return True
    except Exception:
        return False


DB_AVAILABLE = INTEGRATION_TESTS and _db_is_reachable()


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "self-healing-engine"


class TestAlertmanagerWebhook:
    def test_webhook_empty_alerts(self):
        payload = {
            "receiver": "self-healing-engine",
            "status": "firing",
            "alerts": [],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }
        resp = client.post("/webhook/alertmanager", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts_processed"] == 0

    def test_webhook_single_alert(self):
        payload = {
            "receiver": "self-healing-engine",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "CrashLoopBackOff",
                        "severity": "critical",
                        "failure_type": "crash_loop",
                        "app": "api-gateway",
                        "namespace": "production",
                        "pod": "api-gateway-7d8f9",
                        "container": "",
                        "node": "",
                    },
                    "annotations": {
                        "summary": "CrashLoopBackOff for api-gateway-7d8f9",
                        "description": "Pod api-gateway-7d8f9 in production is in CrashLoopBackOff",
                    },
                    "startsAt": "2024-01-01T00:00:00Z",
                    "endsAt": "",
                    "generatorURL": "",
                    "fingerprint": "abc123",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }
        resp = client.post("/webhook/alertmanager", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts_processed"] == 1


@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires PostgreSQL — set SELF_HEALING_INTEGRATION=true and start postgres")
class TestAuditLogs:
    def test_list_audit_logs_empty(self):
        resp = client.get("/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_audit_log_not_found(self):
        resp = client.get(f"/audit/{uuid.uuid4()}")
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main()
