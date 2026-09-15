"""Notifications: Telegram Bot API + Slack webhook via stdlib only."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Tuple


def _post_json(url: str, payload: dict, timeout: int = 15) -> Tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return 200 <= resp.status < 300, body[:1000]
    except Exception as e:
        return False, str(e)[:500]


def send_telegram(token: str, chat_id: str, text: str, timeout: int = 15) -> Tuple[bool, str]:
    if not token or not chat_id:
        return False, "telegram token/chat_id missing"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _post_json(url, {"chat_id": chat_id, "text": text[:4000]}, timeout=timeout)


def send_slack(webhook_url: str, text: str, timeout: int = 15) -> Tuple[bool, str]:
    if not webhook_url:
        return False, "slack webhook missing"
    return _post_json(webhook_url, {"text": text[:3500]}, timeout=timeout)


def dispatch(report, settings) -> dict:
    text = report.to_messenger_text()
    status: dict = {}
    if getattr(settings, "telegram_enabled", False):
        ok, info = send_telegram(settings.telegram_token, settings.telegram_chat_id, text)
        status["telegram"] = {"ok": ok, "info": info}
    if getattr(settings, "slack_enabled", False):
        ok, info = send_slack(settings.slack_webhook_url, text)
        status["slack"] = {"ok": ok, "info": info}
    return status


def parse_chat_id(raw: str) -> str:
    return urllib.parse.quote_plus(raw.strip()) if raw else raw
