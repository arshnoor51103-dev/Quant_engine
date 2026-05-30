#!/usr/bin/env python
"""PostToolUse hook: non-blocking nudge when tests change but LEARNING.md doesn't.

Maintains per-session state in ``.claude/hooks/.state/<session_id>.json`` with
``{"learning_edited": bool, "test_count": int|null}``. When the count of
``def test_`` functions across the repo's top-level ``tests/*.py`` changes and
LEARNING.md was NOT edited this session, prints a single nudge line.

This hook NEVER blocks and NEVER exits non-zero.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(__file__).resolve().parent / ".state"
TESTS_DIR = PROJECT_ROOT / "tests"
TEST_DEF_RE = re.compile(r"^\s*def test_")


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


def _load_state(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"learning_edited": False, "test_count": None}


def _save_state(path: Path, state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:
        pass


def _count_tests() -> int:
    total = 0
    try:
        for py in sorted(TESTS_DIR.glob("*.py")):
            try:
                with py.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if TEST_DEF_RE.match(line):
                            total += 1
            except Exception:
                continue
    except Exception:
        return total
    return total


def _is_under_tests(file_path: str) -> bool:
    try:
        rel = Path(file_path).resolve().relative_to(PROJECT_ROOT)
    except (ValueError, Exception):
        return False
    parts = rel.parts
    return bool(parts) and parts[0] == "tests" and rel.suffix == ".py"


def main() -> int:
    data = _read_input()
    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = "unknown"
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return 0

    state_path = STATE_DIR / f"{session_id}.json"
    state = _load_state(state_path)

    basename = Path(file_path).name

    if basename == "LEARNING.md":
        state["learning_edited"] = True
        _save_state(state_path, state)
        return 0

    if _is_under_tests(file_path):
        new_count = _count_tests()
        prior = state.get("test_count")

        if prior is None:
            state["test_count"] = new_count
            _save_state(state_path, state)
            return 0

        if new_count != prior:
            state["test_count"] = new_count
            _save_state(state_path, state)
            if not state.get("learning_edited"):
                print(
                    f"[nudge] tests changed ({prior}->{new_count}) but no "
                    "LEARNING.md edit this session — consider /learning-entry"
                )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
