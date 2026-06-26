"""Tests for K8s actions using mocked Kubernetes client."""
from unittest.mock import patch, MagicMock

import pytest
from kubernetes.client.rest import ApiException
from app.actions.k8s_actions import restart_pod, scale_deployment, delete_pod


class TestRestartPod:
    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_restart_pod_success(self, mock_get_client):
        mock_core = MagicMock()
        mock_get_client.return_value = (mock_core, MagicMock())

        result = restart_pod(target="pod-1", namespace="default")
        mock_core.delete_namespaced_pod.assert_called_once_with(
            name="pod-1", namespace="default"
        )
        assert result["status"] == "success"

    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_restart_pod_failure(self, mock_get_client):
        mock_core = MagicMock()
        mock_core.delete_namespaced_pod.side_effect = ApiException(http_resp=MagicMock(status=500))
        mock_get_client.return_value = (mock_core, MagicMock())

        result = restart_pod(target="pod-1", namespace="default")
        assert result["status"] == "failed"


class TestScaleDeployment:
    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_scale_up_increases_replicas(self, mock_get_client):
        mock_apps = MagicMock()
        mock_deployment = MagicMock()
        mock_deployment.spec.replicas = 3
        mock_apps.read_namespaced_deployment.return_value = mock_deployment
        mock_get_client.return_value = (MagicMock(), mock_apps)

        result = scale_deployment(
            target="svc-1",
            namespace="default",
            params={"replicas_increase": 2},
            action_type="scale_up",
        )
        assert result["status"] == "success"
        assert "3 → 5" in result["message"]

    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_scale_down_min_one(self, mock_get_client):
        mock_apps = MagicMock()
        mock_deployment = MagicMock()
        mock_deployment.spec.replicas = 1
        mock_apps.read_namespaced_deployment.return_value = mock_deployment
        mock_get_client.return_value = (MagicMock(), mock_apps)

        result = scale_deployment(
            target="svc-1",
            namespace="default",
            params={"replicas_decrease": 5},
            action_type="scale_down",
        )
        assert result["status"] == "success"


class TestDeletePod:
    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_delete_pod_success(self, mock_get_client):
        mock_core = MagicMock()
        mock_get_client.return_value = (mock_core, MagicMock())

        result = delete_pod(target="pod-1", namespace="default")
        mock_core.delete_namespaced_pod.assert_called_once_with(
            name="pod-1", namespace="default"
        )
        assert result["status"] == "success"

    @patch("app.actions.k8s_actions._get_k8s_client")
    def test_delete_pod_failure(self, mock_get_client):
        mock_core = MagicMock()
        mock_core.delete_namespaced_pod.side_effect = ApiException(http_resp=MagicMock(status=500))
        mock_get_client.return_value = (mock_core, MagicMock())

        result = delete_pod(target="pod-1", namespace="default")
        assert result["status"] == "failed"


if __name__ == "__main__":
    pytest.main()
