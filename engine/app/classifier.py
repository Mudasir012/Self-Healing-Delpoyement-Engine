import re
from typing import Any

from .schemas import AlertmanagerAlert, ClassifiedAlert


FAILURE_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "crash_loop": [
        {"field": "labels.alertname", "pattern": r"(?i)crash|CrashLoopBackOff|restart"},
        {"field": "labels.failure_type", "pattern": r"(?i)crash_loop"},
        {"field": "annotations.description", "pattern": r"(?i)crash|restarting"},
    ],
    "high_memory": [
        {"field": "labels.alertname", "pattern": r"(?i)memory|Memory"},
        {"field": "labels.failure_type", "pattern": r"(?i)high_memory"},
    ],
    "high_latency": [
        {"field": "labels.alertname", "pattern": r"(?i)latency|Latency"},
        {"field": "labels.failure_type", "pattern": r"(?i)high_latency"},
    ],
    "disk_full": [
        {"field": "labels.alertname", "pattern": r"(?i)disk|Disk|DiskPressure"},
        {"field": "labels.failure_type", "pattern": r"(?i)disk_full"},
    ],
    "bad_deployment": [
        {"field": "labels.alertname", "pattern": r"(?i)error|Error|deployment|Deployment"},
        {"field": "labels.failure_type", "pattern": r"(?i)bad_deployment"},
    ],
}


def get_field_value(alert: AlertmanagerAlert, field_path: str) -> str:
    parts = field_path.split(".")
    if parts[0] == "labels":
        return getattr(alert.labels, parts[1], "")
    elif parts[0] == "annotations":
        return getattr(alert.annotations, parts[1], "")
    return ""


def classify_alert(alert: AlertmanagerAlert) -> str:
    if alert.labels.failure_type and alert.labels.failure_type != "unknown":
        return alert.labels.failure_type

    for failure_type, patterns in FAILURE_PATTERNS.items():
        for pattern_def in patterns:
            value = get_field_value(alert, pattern_def["field"])
            if re.search(pattern_def["pattern"], value):
                return failure_type
    return "unknown"


def build_classified_alert(alert: AlertmanagerAlert) -> ClassifiedAlert:
    failure_type = classify_alert(alert)

    target = (
        alert.labels.pod
        or alert.labels.app
        or alert.labels.container
        or alert.labels.node
        or "unknown"
    )
    namespace = alert.labels.namespace or "default"

    return ClassifiedAlert(
        failure_type=failure_type,
        severity=alert.labels.severity,
        target=target,
        namespace=namespace,
        alert_data={
            "alertname": alert.labels.alertname,
            "summary": alert.annotations.summary,
            "description": alert.annotations.description,
            "fingerprint": alert.fingerprint,
            "status": alert.status,
            "startsAt": alert.startsAt,
        },
        message=alert.annotations.description or alert.annotations.summary,
    )
