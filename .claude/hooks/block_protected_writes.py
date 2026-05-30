#!/usr/bin/env python
"""PreToolUse hook (Write only): block direct Write to append-only logs.

LEARNING.md and DEEPER_LEARNING.md are append-only history files. A direct
Write would overwrite them, so we deny it and point the operator at Edit /
the /learning-entry skill instead. Registered only for the Write tool, so
Edit-append is always allowed.

Exit code is always 0; the deny decision is communicated via JSON on stdout.
"""

import json
import sys
from pathlib import Path

PROTECTED = {"learning.md", "deeper_learning.md"}

REASON = (
    "LEARNING.md and DEEPER_LEARNING.md are append-only history logs. "
    "A direct Write would overwrite existing entries. Use Edit to append a "
    "new entry, or the /learning-entry skill."
)


def _read_input() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    data = _read_input()
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return 0

    basename = Path(file_path).name.lower()
    if basename in PROTECTED:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        }
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
