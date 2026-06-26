from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AlertmanagerAnnotation(BaseModel):
    summary: str = ""
    description: str = ""


class AlertmanagerLabel(BaseModel):
    alertname: str = ""
    severity: str = ""
    failure_type: str = "unknown"
    app: str = ""
    namespace: str = ""
    pod: str = ""
    container: str = ""
    node: str = ""


class AlertmanagerAlert(BaseModel):
    status: str
    labels: AlertmanagerLabel
    annotations: AlertmanagerAnnotation
    startsAt: str = ""
    endsAt: str = ""
    generatorURL: str = ""
    fingerprint: str = ""


class AlertmanagerWebhook(BaseModel):
    receiver: str = ""
    status: str = ""
    alerts: list[AlertmanagerAlert] = []
    groupLabels: dict[str, Any] = {}
    commonLabels: dict[str, Any] = {}
    commonAnnotations: dict[str, Any] = {}
    externalURL: str = ""


class ClassifiedAlert(BaseModel):
    failure_type: str
    severity: str
    target: str
    namespace: str
    alert_data: dict[str, Any]
    message: str


class ActionResponse(BaseModel):
    audit_log_id: UUID
    action: str
    target: str
    status: str
    message: str


class ApprovalRequest(BaseModel):
    action: str = Field(..., description="approve or reject")


class AuditLogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    failure_type: str
    action: str
    target: str
    namespace: str | None
    status: str
    duration_ms: float | None
    outcome: str | None

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "self-healing-engine"
