#!/usr/bin/env python
"""PostToolUse hook: run pytest only when a src/ or tests/ .py file changes.

Reads a Claude Code hook JSON object from stdin. Fires pytest only when the
edited file lives under the repo's top-level ``src/`` or ``tests/`` directory
and ends with ``.py``. Anything else (docs/, .claude/, non-Python) is ignored.

Exit codes:
    0  -> ignored, or pytest passed (prints one summary line to stdout)
    2  -> pytest failed or timed out (prints last 20 lines to stderr)
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTEST_TIMEOUT_SEC = 110
TAIL_LINES = 20


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


def _relative_to_root(file_path: str) -> Path | None:
    """Return path relative to PROJECT_ROOT, or None if outside the root."""
    try:
        abs_path = Path(file_path).resolve()
    except Exception:
        return None
    try:
        return abs_path.relative_to(PROJECT_ROOT)
    except ValueError:
        return None


def _should_fire(rel: Path) -> bool:
    if rel.suffix != ".py":
        return False
    parts = rel.parts
    if not parts:
        return False
    return parts[0] in ("src", "tests")


def main() -> int:
    data = _read_input()
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return 0

    rel = _relative_to_root(file_path)
    if rel is None or not _should_fire(rel):
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "--tb=short"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=PYTEST_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[hook] pytest timed out after {PYTEST_TIMEOUT_SEC}s",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[hook] pytest could not run: {exc}", file=sys.stderr)
        return 2

    output = proc.stdout or ""
    lines = output.splitlines()
    tail = lines[-TAIL_LINES:]

    if proc.returncode == 0:
        summary = next(
            (ln for ln in reversed(tail) if ln.strip()),
            "(no output)",
        )
        print(f"[hook] pytest: {summary.strip()}")
        return 0

    print("\n".join(tail), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
