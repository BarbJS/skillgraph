"""Severity-based Slack alerts using a Bot User OAuth Token."""

from __future__ import annotations

import os
import time
from threading import Lock
from typing import Any

import requests


class AlertManager:
    def __init__(self) -> None:
        self.enabled = os.getenv("SLACK_ALERTS_ENABLED", "false").casefold() == "true"
        self.token = os.getenv("SLACK_BOT_TOKEN", "")
        self.channel_id = os.getenv("SLACK_CHANNEL_ID", "")
        self.cooldown = int(os.getenv("SLACK_ALERT_COOLDOWN_SECONDS", "900"))
        self._last: dict[str, float] = {}
        self._lock = Lock()

    def notify(self, severity: str, subject: str, details: dict[str, Any]) -> bool:
        severity = severity.casefold()
        if severity not in {"critical", "high", "super_critical"}:
            return False
        if not self.enabled or not self.token or not self.channel_id:
            return False
        now = time.time()
        with self._lock:
            if now - self._last.get(subject, 0) < self.cooldown:
                return False
            self._last[subject] = now
        safe_details = "\n".join(f"• {key}: {value}" for key, value in details.items())
        payload = {
            "channel": self.channel_id,
            "text": f"[{severity.upper()}] SkillGraph observability alert\n{subject}\n{safe_details}",
        }
        try:
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
            return bool(body.get("ok"))
        except (requests.RequestException, ValueError):
            return False
