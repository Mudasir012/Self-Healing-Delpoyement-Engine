import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    Enum,
    JSON,
    ForeignKey,
    Uuid,
)

from .database import Base


class ActionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    running = "running"
    success = "success"
    failed = "failed"
    timed_out = "timed_out"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    failure_type = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    target = Column(String(255), nullable=False)
    namespace = Column(String(100), nullable=True)
    status = Column(Enum(ActionStatus), nullable=False, default=ActionStatus.pending)
    duration_ms = Column(Float, nullable=True)
    outcome = Column(Text, nullable=True)
    alert_data = Column(JSON, nullable=True)
    triggered_by = Column(String(100), default="auto")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    audit_log_id = Column(
        Uuid, ForeignKey("audit_logs.id"), nullable=False
    )
    slack_ts = Column(String(50), nullable=True)
    status = Column(Enum(ActionStatus), nullable=False, default=ActionStatus.pending)
    requested_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)
    responded_by = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class Cooldown(Base):
    __tablename__ = "cooldowns"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    target = Column(String(255), nullable=False)
    failure_type = Column(String(100), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
