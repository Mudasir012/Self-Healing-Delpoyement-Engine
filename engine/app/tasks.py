import time
import uuid
from datetime import datetime, timezone

import structlog
from celery import Celery
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import AuditLog, ActionStatus, Approval

celery_app = Celery(
    "remediation",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.task_time_limit = 120

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def execute_remediation(self, audit_log_id: str, action_type: str | None = None):
    from .actions import ACTION_REGISTRY

    db: Session = SessionLocal()
    try:
        audit_id = uuid.UUID(audit_log_id)
        audit_entry = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
        if not audit_entry:
            logger.error("audit_log_not_found", audit_id=audit_log_id)
            return {"status": "failed", "error": "audit log not found"}

        audit_entry.status = ActionStatus.running
        db.commit()

        handler = ACTION_REGISTRY.get(audit_entry.action)
        if not handler:
            audit_entry.status = ActionStatus.failed
            audit_entry.outcome = f"No handler for action: {audit_entry.action}"
            db.commit()
            return {"status": "failed", "error": audit_entry.outcome}

        start = time.time()

        result = handler(
            target=audit_entry.target,
            namespace=audit_entry.namespace or "default",
            params=audit_entry.alert_data,
            action_type=action_type or audit_entry.action,
        )

        duration_ms = (time.time() - start) * 1000
        audit_entry.duration_ms = duration_ms
        audit_entry.status = ActionStatus(result.get("status", "failed"))
        audit_entry.outcome = result.get("message", "")

        if audit_entry.status == ActionStatus.failed:
            retry = self.retry(exc=Exception(audit_entry.outcome))
            if retry:
                return retry

        db.commit()

        _notify_action(audit_entry)

        return {
            "status": audit_entry.status.value,
            "action": audit_entry.action,
            "target": audit_entry.target,
            "duration_ms": duration_ms,
            "outcome": audit_entry.outcome,
        }
    except Exception as exc:
        logger.error("remediation_task_failed", error=str(exc))
        try:
            audit_id = uuid.UUID(audit_log_id)
            entry = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
            if entry:
                entry.status = ActionStatus.failed
                entry.outcome = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


def _notify_action(audit_entry: AuditLog):
    try:
        from .notifications import send_action_notification

        send_action_notification(
            action=audit_entry.action,
            target=audit_entry.target,
            failure_type=audit_entry.failure_type,
            status=audit_entry.status.value,
            duration_ms=audit_entry.duration_ms,
            outcome=audit_entry.outcome,
        )
    except Exception as e:
        logger.warning("notification_failed", error=str(e))


@celery_app.task
def check_pending_approvals():
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = (
            db.query(Approval)
            .filter(
                Approval.status == ActionStatus.pending,
                Approval.expires_at <= now,
            )
            .all()
        )
        for approval in expired:
            approval.status = ActionStatus.timed_out
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.id == approval.audit_log_id)
                .first()
            )
            if audit:
                audit.status = ActionStatus.timed_out
                audit.outcome = "Approval timed out"
        db.commit()

        if expired:
            logger.info("approvals_timed_out", count=len(expired))
    finally:
        db.close()
