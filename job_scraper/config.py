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
    host = os.environ.get("EMAIL_HOST", "").strip()
    port_raw = (os.environ.get("EMAIL_PORT") or "").strip() or "587"
    port = int(port_raw)
    user = os.environ.get("EMAIL_USER", "").strip()
    password = os.environ.get("EMAIL_PASS", "")
    to = (os.environ.get("EMAIL_TO") or user).strip()
    return EmailConfig(host=host, port=port, user=user, password=password, to=to)


def is_configured(cfg: EmailConfig) -> bool:
    return bool(cfg.host and cfg.user and cfg.password and cfg.to)
