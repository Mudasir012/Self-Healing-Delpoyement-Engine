import structlog
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ..config import settings

logger = structlog.get_logger(__name__)


def _get_k8s_client() -> client.CoreV1Api:
    if settings.k8s_in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config(config_file=settings.k8s_config_path)
    return client.CoreV1Api()


def disk_cleanup(target: str, namespace: str, **kwargs) -> dict:
    core_v1 = _get_k8s_client()
    node_name = target

    label_selector = f"kubernetes.io/hostname={node_name}"
    try:
        pods = core_v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node_name}",
            label_selector="app in (fluentd, log-agent, filebeat)",
        )
        deleted = 0
        for pod in pods.items:
            core_v1.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
            )
            deleted += 1

        logger.info("disk_cleanup_completed", node=node_name, pods_deleted=deleted)
        return {
            "status": "success",
            "message": f"Cleaned up {deleted} agent pods on {node_name} to free disk",
        }
    except ApiException as e:
        logger.error("disk_cleanup_failed", node=node_name, error=str(e))
        return {"status": "failed", "message": str(e)}


def log_rotation(target: str, namespace: str, **kwargs) -> dict:
    core_v1 = _get_k8s_client()
    try:
        pods = core_v1.list_namespaced_pod(
            namespace=namespace,
            field_selector=f"metadata.name={target}",
        )
        if not pods.items:
            return {"status": "failed", "message": f"Pod {target} not found"}

        log_cmd = ["sh", "-c", "truncate -s 0 /var/log/*.log 2>/dev/null; echo 'logs rotated'"]

        resp = core_v1.connect_get_namespaced_pod_exec(
            name=target,
            namespace=namespace,
            command=log_cmd,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        logger.info("log_rotation_completed", pod=target, namespace=namespace)
        return {"status": "success", "message": f"Logs rotated for {target}"}
    except ApiException as e:
        logger.error("log_rotation_failed", pod=target, error=str(e))
        return {"status": "failed", "message": str(e)}
