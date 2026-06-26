import structlog
import httpx

from ..config import settings

logger = structlog.get_logger(__name__)


def rollback_deployment(
    target: str, namespace: str, params: dict | None = None, **kwargs
) -> dict:
    revision = (params or {}).get("revision", "")
    app_name = target

    headers = {
        "Authorization": f"Bearer {settings.argo_token}",
        "Content-Type": "application/json",
    }

    payload: dict = {"name": app_name, "rollback": True}
    if revision:
        payload["revision"] = revision

    try:
        resp = httpx.post(
            f"https://{settings.argo_server}/api/v1/applications/{app_name}/rollback",
            headers=headers,
            json=payload,
            verify=False,
            timeout=30,
        )
        if resp.is_success:
            logger.info("rollback_initiated", app=app_name, revision=revision)
            return {
                "status": "success",
                "message": f"Rollback initiated for {app_name} via Argo CD",
            }
        else:
            logger.error("rollback_failed", app=app_name, error=resp.text)
            return {"status": "failed", "message": resp.text}
    except Exception as e:
        logger.error("rollback_exception", app=app_name, error=str(e))
        return {"status": "failed", "message": str(e)}
