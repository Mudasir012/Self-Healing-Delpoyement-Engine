from .k8s_actions import restart_pod, scale_deployment, delete_pod
from .gitops import rollback_deployment
from .infra_actions import disk_cleanup, log_rotation

ACTION_REGISTRY = {
    "restart_pod": restart_pod,
    "scale_up": scale_deployment,
    "scale_down": scale_deployment,
    "rollback": rollback_deployment,
    "disk_cleanup": disk_cleanup,
    "log_rotation": log_rotation,
    "delete_pod": delete_pod,
}

__all__ = ["ACTION_REGISTRY"]
