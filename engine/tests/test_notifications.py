from unittest.mock import patch, MagicMock

from app.notifications import send_notification, send_action_notification


class TestNotifications:
    @patch("app.notifications.get_slack_client")
    def test_send_notification_no_client(self, mock_get):
        mock_get.return_value = None
        result = send_notification("test")
        assert result is None

    @patch("app.notifications.get_slack_client")
    def test_send_notification_success(self, mock_get):
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "12345.6789"}
        mock_get.return_value = mock_client

        result = send_notification("Hello")
        assert result == "12345.6789"
        mock_client.chat_postMessage.assert_called_once_with(
            channel="#remediation", text="Hello"
        )

    @patch("app.notifications.get_slack_client")
    def test_send_action_notification_success(self, mock_get):
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "12345.6789"}
        mock_get.return_value = mock_client

        send_action_notification(
            action="restart_pod",
            target="pod-1",
            failure_type="crash_loop",
            status="success",
            duration_ms=320.5,
        )

        call_args = mock_client.chat_postMessage.call_args[1]["text"]
        assert "restart_pod" in call_args
        assert "pod-1" in call_args
        assert "crash_loop" in call_args
        assert "success" in call_args
        assert "320" in call_args


if __name__ == "__main__":
    pytest.main()
