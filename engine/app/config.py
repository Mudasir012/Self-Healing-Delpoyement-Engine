from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://remediator:remediator@localhost:5432/self_healing"
    redis_url: str = "redis://localhost:6379/0"
    slack_bot_token: str = ""
    slack_channel: str = "#remediation"
    k8s_in_cluster: bool = False
    k8s_config_path: str = "/app/kube-config"
    log_level: str = "INFO"
    rules_path: str = "/app/rules.yaml"
    approval_timeout_seconds: int = 300
    argo_server: str = "argocd-server.argocd.svc.cluster.local"
    argo_token: str = ""
    metrics_port: int = 8000


settings = Settings()
