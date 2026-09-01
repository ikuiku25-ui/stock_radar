from __future__ import annotations

import pytest

from stock_radar.notification.email_notifier import (
    EmailConfig,
    EmailConfigError,
    send_email_notification,
)


def _clear_email_env(monkeypatch):
    for var in (
        "STOCK_RADAR_SMTP_HOST", "STOCK_RADAR_SMTP_PORT", "STOCK_RADAR_SMTP_USER",
        "STOCK_RADAR_SMTP_PASSWORD", "STOCK_RADAR_NOTIFY_EMAIL_TO", "STOCK_RADAR_NOTIFY_EMAIL_FROM",
    ):
        monkeypatch.delenv(var, raising=False)


def _set_valid_email_env(monkeypatch):
    monkeypatch.setenv("STOCK_RADAR_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("STOCK_RADAR_SMTP_USER", "user@example.com")
    monkeypatch.setenv("STOCK_RADAR_SMTP_PASSWORD", "secret")
    monkeypatch.setenv("STOCK_RADAR_NOTIFY_EMAIL_TO", "me@example.com")


def test_validate_raises_when_all_missing(monkeypatch):
    _clear_email_env(monkeypatch)
    config = EmailConfig()
    with pytest.raises(EmailConfigError) as exc_info:
        config.validate()
    message = str(exc_info.value)
    assert "STOCK_RADAR_SMTP_HOST" in message
    assert "STOCK_RADAR_NOTIFY_EMAIL_TO" in message


def test_validate_passes_with_all_required_vars(monkeypatch):
    _clear_email_env(monkeypatch)
    _set_valid_email_env(monkeypatch)
    EmailConfig().validate()  # should not raise


def test_from_address_defaults_to_username(monkeypatch):
    _clear_email_env(monkeypatch)
    _set_valid_email_env(monkeypatch)
    config = EmailConfig()
    assert config.from_address == "user@example.com"


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = None
        self.sent_message = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, msg):
        self.sent_message = msg


def test_send_email_notification_uses_smtp_correctly(monkeypatch):
    _clear_email_env(monkeypatch)
    _set_valid_email_env(monkeypatch)
    FakeSMTP.instances.clear()
    monkeypatch.setattr("stock_radar.notification.email_notifier.smtplib.SMTP", FakeSMTP)

    send_email_notification("件名", "本文")

    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("user@example.com", "secret")
    assert smtp.sent_message["Subject"] == "件名"
    assert smtp.sent_message["To"] == "me@example.com"


def test_send_email_notification_raises_without_config(monkeypatch):
    _clear_email_env(monkeypatch)
    with pytest.raises(EmailConfigError):
        send_email_notification("件名", "本文")
