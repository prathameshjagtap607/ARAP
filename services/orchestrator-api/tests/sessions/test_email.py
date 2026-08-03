import logging
from unittest.mock import MagicMock, patch

from src.modules.sessions.email import send_invite_email


def test_send_invite_email_stdout_fallback(caplog):
    """When no SMTP or SendGrid configured, logs warning and returns False."""
    with patch("src.modules.sessions.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        mock_settings.SENDGRID_API_KEY = ""
        with caplog.at_level(logging.WARNING):
            result = send_invite_email(
                to="alice@example.com",
                link="http://localhost:3000/assessment/abc?token=tok",
                job_title="Engineer",
                duration_minutes=60,
            )
    assert result is False
    assert "no email provider" in caplog.text.lower()


def test_send_invite_email_smtp(monkeypatch):
    """When SMTP_HOST set, calls smtplib.SMTP and returns True."""
    with patch("src.modules.sessions.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@arap.dev"
        mock_settings.SENDGRID_API_KEY = ""
        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            result = send_invite_email(
                to="alice@example.com",
                link="http://localhost:3000/assessment/abc?token=tok",
                job_title="Engineer",
                duration_minutes=60,
            )
    assert result is True
    mock_smtp.__enter__.return_value.sendmail.assert_called_once()


def test_send_invite_email_falls_back_to_smtp_when_sendgrid_fails():
    """When SendGrid is configured but fails, falls back to SMTP instead of giving up."""
    with patch("src.modules.sessions.email.settings") as mock_settings:
        mock_settings.SENDGRID_API_KEY = "sg-fake-key"
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@arap.dev"

        with patch("src.modules.sessions.email._send_via_sendgrid", return_value=False), \
             patch("src.modules.sessions.email._send_via_smtp", return_value=True) as mock_smtp_send:
            result = send_invite_email(
                to="alice@example.com",
                link="http://localhost:3000/assessment/abc?token=tok",
                job_title="Engineer",
                duration_minutes=60,
            )

    assert result is True
    mock_smtp_send.assert_called_once()
