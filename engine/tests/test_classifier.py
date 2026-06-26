import pytest
from app.classifier import classify_alert, build_classified_alert
from app.schemas import AlertmanagerAlert, AlertmanagerLabel, AlertmanagerAnnotation


def make_alert(
    alertname: str = "",
    severity: str = "warning",
    failure_type: str = "unknown",
    app: str = "",
    namespace: str = "default",
    pod: str = "",
    container: str = "",
    node: str = "",
    summary: str = "",
    description: str = "",
) -> AlertmanagerAlert:
    return AlertmanagerAlert(
        status="firing",
        labels=AlertmanagerLabel(
            alertname=alertname,
            severity=severity,
            failure_type=failure_type,
            app=app,
            namespace=namespace,
            pod=pod,
            container=container,
            node=node,
        ),
        annotations=AlertmanagerAnnotation(summary=summary, description=description),
        startsAt="2024-01-01T00:00:00Z",
    )


class TestClassifier:
    def test_classify_crash_loop_by_label(self):
        alert = make_alert(failure_type="crash_loop")
        assert classify_alert(alert) == "crash_loop"

    def test_classify_crash_loop_by_alertname(self):
        alert = make_alert(alertname="CrashLoopBackOff")
        assert classify_alert(alert) == "crash_loop"

    def test_classify_high_memory_by_label(self):
        alert = make_alert(failure_type="high_memory")
        assert classify_alert(alert) == "high_memory"

    def test_classify_high_latency(self):
        alert = make_alert(alertname="HighLatency")
        assert classify_alert(alert) == "high_latency"

    def test_classify_disk_full(self):
        alert = make_alert(alertname="DiskPressure")
        assert classify_alert(alert) == "disk_full"

    def test_classify_bad_deployment(self):
        alert = make_alert(failure_type="bad_deployment")
        assert classify_alert(alert) == "bad_deployment"

    def test_classify_unknown(self):
        alert = make_alert(alertname="SomeObscureAlert", description="Something weird happened")
        assert classify_alert(alert) == "unknown"

    def test_classify_fallback_to_description(self):
        alert = make_alert(description="Pod api-gateway is restarting frequently")
        assert classify_alert(alert) == "crash_loop"

    def test_build_classified_alert_sets_fields(self):
        alert = make_alert(
            failure_type="crash_loop",
            pod="api-gateway-7d8f9",
            namespace="production",
            description="Pod is crashing",
        )
        classified = build_classified_alert(alert)
        assert classified.failure_type == "crash_loop"
        assert classified.target == "api-gateway-7d8f9"
        assert classified.namespace == "production"
        assert classified.severity == "warning"


if __name__ == "__main__":
    pytest.main()
