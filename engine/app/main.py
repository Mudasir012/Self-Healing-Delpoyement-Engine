import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .config import settings
from .database import init_db, get_db, SessionLocal
from .models import AuditLog, Approval, ActionStatus, Base
from .schemas import (
    AlertmanagerWebhook,
    ActionResponse,
    ApprovalRequest,
    AuditLogResponse,
    HealthResponse,
)
from .classifier import build_classified_alert
from .rule_engine import process_alert
from .notifications import send_approval_request, send_action_notification
from .tasks import execute_remediation, check_pending_approvals

logger = structlog.get_logger(__name__)

ALERTS_RECEIVED = Counter("engine_alerts_received_total", "Total alerts received")
ACTIONS_TRIGGERED = Counter("engine_actions_triggered_total", "Total actions triggered", ["action", "status"])
PROCESSING_DURATION = Histogram("engine_processing_duration_seconds", "Alert processing duration", ["failure_type"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_self_healing_engine")
    init_db()
    from .database import engine
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("shutting_down_self_healing_engine")


app = FastAPI(
    title="Self-Healing Deployment Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return {"detail": "Internal server error"}, 500


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook/alertmanager")
async def alertmanager_webhook(
    payload: AlertmanagerWebhook, request: Request
):
    logger.info("alertmanager_webhook_received", alert_count=len(payload.alerts))

    for alert in payload.alerts:
        ALERTS_RECEIVED.inc()
        classified = build_classified_alert(alert)
        logger.info(
            "alert_classified",
            failure_type=classified.failure_type,
            target=classified.target,
            severity=classified.severity,
        )

        audit_logs = process_alert(classified)

        for audit_entry in audit_logs:
            ACTIONS_TRIGGERED.labels(
                action=audit_entry.action, status=audit_entry.status.value
            ).inc()

            if audit_entry.status == ActionStatus.approved:
                execute_remediation.delay(str(audit_entry.id))
            elif audit_entry.status == ActionStatus.pending:
                send_approval_request(
                    action=audit_entry.action,
                    target=audit_entry.target,
                    failure_type=audit_entry.failure_type,
                    audit_id=str(audit_entry.id),
                    namespace=audit_entry.namespace or "default",
                )

    return {"status": "ok", "alerts_processed": len(payload.alerts)}


@app.post("/webhook/slack/actions")
async def slack_action_webhook(request: Request):
    form = await request.form()
    payload_str = form.get("payload", "{}")
    import json
    data = json.loads(payload_str)

    actions = data.get("actions", [])
    if not actions:
        raise HTTPException(status_code=400, detail="No actions found")

    action_id = actions[0].get("value", "")
    action_type = actions[0].get("name", "")

    return await handle_approval(audit_id=action_id, action=action_type)


@app.post("/approve/{audit_id}")
@app.post("/reject/{audit_id}")
async def handle_approval_endpoint(
    audit_id: str, action: str = Query(None), db: Session = Depends(get_db)
):
    path_action = audit_id.split("/")[-1]
    return await handle_approval(audit_id=audit_id, action=action or path_action)


async def handle_approval(audit_id: str, action: str):
    db = SessionLocal()
    try:
        audit_uuid = uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID")

    db = SessionLocal()
    try:
        audit_entry = db.query(AuditLog).filter(AuditLog.id == audit_uuid).first()
        if not audit_entry:
            raise HTTPException(status_code=404, detail="Audit log not found")

        approval = (
            db.query(Approval)
            .filter(
                Approval.audit_log_id == audit_uuid,
                Approval.status == ActionStatus.pending,
            )
            .first()
        )
        if not approval:
            raise HTTPException(status_code=400, detail="No pending approval found")

        if action == "approve":
            approval.status = ActionStatus.approved
            approval.responded_at = datetime.now(timezone.utc)
            audit_entry.status = ActionStatus.approved
            db.commit()

            execute_remediation.delay(str(audit_entry.id))

            send_action_notification(
                action=audit_entry.action,
                target=audit_entry.target,
                failure_type=audit_entry.failure_type,
                status="approved",
            )

            return ActionResponse(
                audit_log_id=audit_uuid,
                action=audit_entry.action,
                target=audit_entry.target,
                status="approved",
                message=f"Approval granted — executing {audit_entry.action}",
            )

        elif action == "reject":
            approval.status = ActionStatus.rejected
            approval.responded_at = datetime.now(timezone.utc)
            audit_entry.status = ActionStatus.rejected
            audit_entry.outcome = "Rejected by operator"
            db.commit()

            send_action_notification(
                action=audit_entry.action,
                target=audit_entry.target,
                failure_type=audit_entry.failure_type,
                status="rejected",
            )

            return ActionResponse(
                audit_log_id=audit_uuid,
                action=audit_entry.action,
                target=audit_entry.target,
                status="rejected",
                message="Action rejected by operator",
            )

        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    finally:
        db.close()


@app.get("/audit", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    failure_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if failure_type:
        query = query.filter(AuditLog.failure_type == failure_type)
    if status:
        query = query.filter(AuditLog.status == status)
    query = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit)
    return query.all()


@app.get("/audit/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(audit_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return entry
