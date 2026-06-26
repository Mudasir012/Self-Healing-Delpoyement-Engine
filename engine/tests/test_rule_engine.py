import tempfile
import os
from datetime import datetime, timezone, timedelta

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AuditLog, Cooldown, ActionStatus
from app.rule_engine import (
    load_rules,
    get_matching_rules,
    is_on_cooldown,
    set_cooldown,
    process_alert,
)
from app.schemas import ClassifiedAlert


SAMPLE_RULES = {
    "rules": [
        {
            "condition": "crash_loop",
            "action": "restart_pod",
            "cooldown": 300,
            "approval_required": False,
        },
        {
            "condition": "high_memory",
            "action": "scale_up",
            "params": {"replicas_increase": 2},
            "cooldown": 600,
            "approval_required": True,
        },
        {
            "condition": "bad_deployment",
            "action": "rollback",
            "cooldown": 0,
            "approval_required": True,
        },
    ]
}


@pytest.fixture
def rules_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(SAMPLE_RULES, f)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


class TestLoadRules:
    def test_load_rules_from_file(self, rules_file):
        import app.rule_engine as re
        re.settings.rules_path = rules_file
        rules = load_rules()
        assert len(rules) == 3
        assert rules[0]["condition"] == "crash_loop"

    def test_load_rules_file_not_found(self):
        import app.rule_engine as re
        re.settings.rules_path = "/nonexistent/rules.yaml"
        rules = load_rules()
        assert rules == []


class TestGetMatchingRules:
    def test_finds_matching_rules(self):
        classified = ClassifiedAlert(
            failure_type="crash_loop",
            severity="critical",
            target="pod-1",
            namespace="default",
            alert_data={},
            message="test",
        )
        matches = get_matching_rules(classified, SAMPLE_RULES["rules"])
        assert len(matches) == 1
        assert matches[0]["action"] == "restart_pod"

    def test_no_match_returns_empty(self):
        classified = ClassifiedAlert(
            failure_type="disk_full",
            severity="critical",
            target="node-1",
            namespace="default",
            alert_data={},
            message="test",
        )
        matches = get_matching_rules(classified, SAMPLE_RULES["rules"])
        assert matches == []


class TestCooldown:
    def test_is_on_cooldown_false_when_not_set(self, db_session):
        assert is_on_cooldown(db_session, "pod-1", "crash_loop") is False

    def test_is_on_cooldown_true_when_active(self, db_session):
        set_cooldown(db_session, "pod-1", "crash_loop", 300)
        assert is_on_cooldown(db_session, "pod-1", "crash_loop") is True

    def test_is_on_cooldown_false_when_expired(self, db_session):
        cd = Cooldown(
            target="pod-1",
            failure_type="crash_loop",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        db_session.add(cd)
        db_session.commit()
        assert is_on_cooldown(db_session, "pod-1", "crash_loop") is False


class TestProcessAlert:
    def test_process_alert_creates_audit_log(self, rules_file, db_session):
        import app.rule_engine as re
        re.settings.rules_path = rules_file

        classified = ClassifiedAlert(
            failure_type="crash_loop",
            severity="critical",
            target="api-gateway-7d8f9",
            namespace="production",
            alert_data={"alertname": "CrashLoopBackOff"},
            message="Pod is crashing",
        )

        logs = process_alert(classified, db=db_session)
        assert len(logs) == 1
        assert logs[0].failure_type == "crash_loop"
        assert logs[0].action == "restart_pod"
        assert logs[0].target == "api-gateway-7d8f9"
        assert logs[0].status == ActionStatus.approved

    def test_process_alert_approval_required(self, rules_file, db_session):
        import app.rule_engine as re
        re.settings.rules_path = rules_file

        classified = ClassifiedAlert(
            failure_type="high_memory",
            severity="critical",
            target="checkout-service",
            namespace="production",
            alert_data={},
            message="High memory",
        )

        logs = process_alert(classified, db=db_session)
        assert len(logs) == 1
        assert logs[0].status == ActionStatus.pending

    def test_process_alert_cooldown_respects(self, rules_file, db_session):
        import app.rule_engine as re
        re.settings.rules_path = rules_file

        classified = ClassifiedAlert(
            failure_type="crash_loop",
            severity="critical",
            target="api-gateway-7d8f9",
            namespace="production",
            alert_data={},
            message="Pod is crashing",
        )

        logs1 = process_alert(classified, db=db_session)
        assert len(logs1) == 1

        logs2 = process_alert(classified, db=db_session)
        assert len(logs2) == 0


if __name__ == "__main__":
    pytest.main()
