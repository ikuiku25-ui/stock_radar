"""Email notification (spec §5) via SMTP, stdlib `smtplib` only (no extra
dependency). Credentials come ONLY from environment variables — never
hardcode them or store them in the DB/repo. See README for the variable
names and setup notes (e.g. Gmail requires an app password, not your
regular account password, when 2FA is enabled).
"""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional


class EmailConfigError(RuntimeError):
    pass


class EmailConfig:
    def __init__(self) -> None:
        self.host: Optional[str] = os.environ.get("STOCK_RADAR_SMTP_HOST")
        self.port: int = int(os.environ.get("STOCK_RADAR_SMTP_PORT", "587"))
        self.username: Optional[str] = os.environ.get("STOCK_RADAR_SMTP_USER")
        self.password: Optional[str] = os.environ.get("STOCK_RADAR_SMTP_PASSWORD")
        self.to_address: Optional[str] = os.environ.get("STOCK_RADAR_NOTIFY_EMAIL_TO")
        self.from_address: Optional[str] = os.environ.get(
            "STOCK_RADAR_NOTIFY_EMAIL_FROM", self.username
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("STOCK_RADAR_SMTP_HOST", self.host),
                ("STOCK_RADAR_SMTP_USER", self.username),
                ("STOCK_RADAR_SMTP_PASSWORD", self.password),
                ("STOCK_RADAR_NOTIFY_EMAIL_TO", self.to_address),
            )
            if not value
        ]
        if missing:
            raise EmailConfigError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )


def send_email_notification(
    subject: str, body: str, config: Optional[EmailConfig] = None
) -> None:
    config = config or EmailConfig()
    config.validate()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.from_address
    msg["To"] = config.to_address

    with smtplib.SMTP(config.host, config.port, timeout=15) as server:
        server.starttls()
        server.login(config.username, config.password)
        server.send_message(msg)
