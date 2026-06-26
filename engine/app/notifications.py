import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import settings

logger = structlog.get_logger(__name__)


def get_slack_client() -> WebClient | None:
    if not settings.slack_bot_token:
        return None
    return WebClient(token=settings.slack_bot_token)


def send_notification(message: str) -> str | None:
    client = get_slack_client()
    if not client:
        logger.info("Slack not configured — skipping notification")
        return None
    try:
        resp = client.chat_postMessage(channel=settings.slack_channel, text=message)
        ts = resp.get("ts")
        logger.info("slack_notification_sent", ts=ts)
        return ts
    except SlackApiError as e:
        logger.error("slack_notification_failed", error=str(e))
        return None


def send_approval_request(
    action: str, target: str, failure_type: str, audit_id: str, namespace: str
) -> str | None:
    message = (
        f"⏳ *Approval Required*\n"
        f"*Action:* {action}\n"
        f"*Target:* {target}\n"
        f"*Namespace:* {namespace}\n"
        f"*Failure Type:* {failure_type}\n"
        f"*Audit ID:* `{audit_id}`\n"
        f"_Respond with:_ `/approve {audit_id}` or `/reject {audit_id}`"
    )
    return send_notification(message)


def send_action_notification(
    action: str,
    target: str,
    failure_type: str,
    status: str,
    duration_ms: float | None = None,
    outcome: str | None = None,
):
    icon = {
        "success": "✅",
        "failed": "❌",
        "running": "🔄",
        "rejected": "🚫",
        "timed_out": "⏰",
    }.get(status, "ℹ️")

    duration_str = f" ({duration_ms:.0f}ms)" if duration_ms else ""
    outcome_str = f"\n  _Outcome:_ {outcome}" if outcome else ""

    message = (
        f"{icon} *Auto-Remediation: {status}*\n"
        f"  *Action:* {action}\n"
        f"  *Target:* {target}\n"
        f"  *Failure:* {failure_type}{duration_str}{outcome_str}"
    )
    send_notification(message)
