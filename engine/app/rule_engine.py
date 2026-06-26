import os
from datetime import datetime, timezone, timedelta
from typing import Any

import yaml
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import AuditLog, Approval, ActionStatus, Cooldown
from .schemas import ClassifiedAlert


def load_rules() -> list[dict[str, Any]]:
    path = settings.rules_path
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("rules", [])


def get_matching_rules(
    classified: ClassifiedAlert, rules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        r for r in rules if r["condition"] == classified.failure_type
    ]


def is_on_cooldown(db: Session, target: str, failure_type: str) -> bool:
    now = datetime.now(timezone.utc)
    existing = (
        db.query(Cooldown)
        .filter(
            Cooldown.target == target,
            Cooldown.failure_type == failure_type,
            Cooldown.expires_at > now,
        )
        .first()
    )
    return existing is not None


def set_cooldown(
    db: Session, target: str, failure_type: str, cooldown_seconds: int
):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
    cd = Cooldown(target=target, failure_type=failure_type, expires_at=expires_at)
    db.add(cd)
    db.commit()


def create_approval(db: Session, audit_log: AuditLog):
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.approval_timeout_seconds
    )
    approval = Approval(
        audit_log_id=audit_log.id,
        status=ActionStatus.pending,
        expires_at=expires_at,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def process_alert(
    classified: ClassifiedAlert, db: Session | None = None
) -> list[AuditLog]:
    own_db = db is None
    if own_db:
        db = SessionLocal()

    try:
        rules = load_rules()
        matching = get_matching_rules(classified, rules)

        if not matching:
            return []

        audit_logs = []

        for rule in matching:
            target = classified.target
            failure_type = classified.failure_type

            if is_on_cooldown(db, target, failure_type):
                continue

            action = rule["action"]
            params = rule.get("params", {})
            approval_required = rule.get("approval_required", False)
            cooldown = rule.get("cooldown", 300)

            audit_entry = AuditLog(
                failure_type=failure_type,
                action=action,
                target=target,
                namespace=classified.namespace,
                status=ActionStatus.pending,
                alert_data=classified.alert_data,
            )
            db.add(audit_entry)
            db.commit()
            db.refresh(audit_entry)

            set_cooldown(db, target, failure_type, cooldown)

            if approval_required:
                create_approval(db, audit_entry)
                audit_entry.status = ActionStatus.pending
            else:
                audit_entry.status = ActionStatus.approved

            db.commit()
            audit_logs.append(audit_entry)

        return audit_logs
    finally:
        if own_db and db:
            db.close()
