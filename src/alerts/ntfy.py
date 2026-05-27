"""
HTTP transport for ntfy.sh push notifications.

ntfy.sh POST API: https://docs.ntfy.sh/publish/
"""
from __future__ import annotations

import logging

import requests

_BASE_URL = "https://ntfy.sh"
_TIMEOUT = 5  # seconds


def send_alert(
    topic: str,
    title: str,
    message: str,
    priority: int = 3,
    tags: list[str] | None = None,
) -> None:
    """
    POST a push notification to ntfy.sh.

    Args:
        topic:    ntfy.sh topic name (public unless self-hosted).
        title:    Short notification header.
        message:  Body text shown in the notification.
        priority: 1 (min) – 5 (urgent). Default 3 = normal.
        tags:     Optional emoji tags. See https://docs.ntfy.sh/emojis/

    Never raises — network failures are logged at WARNING and dropped.
    The recommendation pipeline must not fail because an alert failed.
    """
    headers: dict[str, str] = {
        "X-Title": title,
        "X-Priority": str(priority),
    }
    if tags:
        headers["X-Tags"] = ",".join(tags)

    try:
        requests.post(
            f"{_BASE_URL}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=_TIMEOUT,
        )
    except (requests.RequestException, OSError) as exc:
        logging.warning("ntfy.sh alert failed — %s", exc)
