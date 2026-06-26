import structlog
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ..config import settings

logger = structlog.get_logger(__name__)


def _get_k8s_client() -> tuple[client.CoreV1Api, client.AppsV1Api]:
    if settings.k8s_in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config(config_file=settings.k8s_config_path)
    return client.CoreV1Api(), client.AppsV1Api()


def restart_pod(target: str, namespace: str, **kwargs) -> dict:
    core_v1, _ = _get_k8s_client()
    try:
        core_v1.delete_namespaced_pod(name=target, namespace=namespace)
        logger.info("pod_restarted", pod=target, namespace=namespace)
        return {"status": "success", "message": f"Pod {target} deleted — ReplicaSet will recreate"}
    except ApiException as e:
        logger.error("pod_restart_failed", pod=target, error=str(e))
        return {"status": "failed", "message": str(e)}


def scale_deployment(
    target: str, namespace: str, params: dict | None = None, **kwargs
) -> dict:
    _, apps_v1 = _get_k8s_client()
    action_type = kwargs.get("action_type", "scale_up")

    try:
        deployment = apps_v1.read_namespaced_deployment(name=target, namespace=namespace)
        current_replicas = deployment.spec.replicas

        if action_type == "scale_up":
            increase = (params or {}).get("replicas_increase", 1)
            new_replicas = current_replicas + increase
        else:
            decrease = (params or {}).get("replicas_decrease", 1)
            new_replicas = max(1, current_replicas - decrease)

        if new_replicas == current_replicas:
            return {"status": "success", "message": "Replicas unchanged"}

        body = {"spec": {"replicas": new_replicas}}
        apps_v1.patch_namespaced_deployment_scale(
            name=target, namespace=namespace, body=body
        )
        logger.info(
            "deployment_scaled",
            deployment=target,
            from_replicas=current_replicas,
            to_replicas=new_replicas,
        )
        return {
            "status": "success",
            "message": f"Scaled {target} from {current_replicas} → {new_replicas}",
        }
    except ApiException as e:
        logger.error("scale_failed", deployment=target, error=str(e))
        return {"status": "failed", "message": str(e)}


def delete_pod(target: str, namespace: str, **kwargs) -> dict:
    core_v1, _ = _get_k8s_client()
    try:
        core_v1.delete_namespaced_pod(name=target, namespace=namespace)
        logger.info("pod_deleted", pod=target, namespace=namespace)
        return {"status": "success", "message": f"Pod {target} deleted"}
    except ApiException as e:
        logger.error("pod_delete_failed", pod=target, error=str(e))
        return {"status": "failed", "message": str(e)}
