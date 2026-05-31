"""
HTTP transport for ntfy.sh push notifications.

ntfy.sh POST API: https://docs.ntfy.sh/publish/
"""
from __future__ import annotations

import logging

import requests

_BASE_URL = "https://ntfy.sh"
_TIMEOUT = 5  # seconds

# HTTP header values must be latin-1 (RFC 7230; enforced by requests). ntfy
# carries the title in X-Title and tags in X-Tags, so any non-latin-1 char in
# a title/tag (em-dash, arrow, curly quotes, …) raises UnicodeEncodeError
# inside requests *before* the POST. Map common Unicode punctuation to readable
# ASCII; anything else outside latin-1 is replaced so a header can never crash
# an alert. The message body is unaffected — it is sent as UTF-8 bytes.
_HEADER_UNICODE_MAP = {
    "—": "-",    # — em dash
    "–": "-",    # – en dash
    "→": "->",   # → right arrow
    "…": "...",  # … ellipsis
    "‘": "'",    # ' left single quote
    "’": "'",    # ' right single quote
    "“": '"',    # " left double quote
    "”": '"',    # " right double quote
}


def _latin1_header(value: str) -> str:
    """Return ``value`` made safe for a latin-1 HTTP header.

    Common Unicode punctuation is mapped to readable ASCII; any remaining
    character outside latin-1 is replaced with ``?`` so the value always
    encodes and ``requests`` never raises ``UnicodeEncodeError``.

    Args:
        value: Raw header text (title or comma-joined tags).

    Returns:
        A latin-1-encodable string.
    """
    for unicode_char, ascii_repl in _HEADER_UNICODE_MAP.items():
        value = value.replace(unicode_char, ascii_repl)
    return value.encode("latin-1", "replace").decode("latin-1")


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
        "X-Title": _latin1_header(title),
        "X-Priority": str(priority),
    }
    if tags:
        headers["X-Tags"] = _latin1_header(",".join(tags))

    try:
        requests.post(
            f"{_BASE_URL}/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=_TIMEOUT,
        )
    except (requests.RequestException, OSError) as exc:
        logging.warning("ntfy.sh alert failed — %s", exc)
