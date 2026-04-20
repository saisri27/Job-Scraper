"""Load email configuration from environment variables / GitHub Secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    to: str


def load() -> EmailConfig:
    host = os.environ.get("EMAIL_HOST", "")
    port = int(os.environ.get("EMAIL_PORT", "587"))
    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASS", "")
    to = os.environ.get("EMAIL_TO", user)
    return EmailConfig(host=host, port=port, user=user, password=password, to=to)


def is_configured(cfg: EmailConfig) -> bool:
    return bool(cfg.host and cfg.user and cfg.password and cfg.to)
