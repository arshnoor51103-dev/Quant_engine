#!/usr/bin/env python
"""PreToolUse hook (Edit|Write): enforce CLAUDE.md Hard Constraint 4.

The signal path is deterministic math only. No LLM/AI-inference SDK and no
network client may be imported under ``src/signals/`` — a signal reads local
price_data / the SQLite DB, never a live model or remote endpoint. This hook
denies any Edit/Write that *introduces* such an import in the signal path.

Scope is deliberately narrow (``src/signals/``) to keep false positives near
zero. To widen it later (e.g. the signal-combination step), add path segments
to ``_SIGNAL_PATH_SEGMENTS``.

Detection matches *import statements only* (via regex on each line), so a
mention of "openai" in a comment, string, or variable name does not trip the
guard. Dynamic ``__import__("openai")`` is out of scope — this is a guardrail,
not a sandbox.

Exit code is always 0; the deny decision is communicated via JSON on stdout,
mirroring block_protected_writes.py.
"""
from __future__ import annotations

import json
import re
import sys

# Path segments that mark the signal path. A file is guarded if any segment
# appears in its (slash-normalized) path.
_SIGNAL_PATH_SEGMENTS = ("src/signals/",)

# LLM / AI-inference SDK roots and network-client roots. A module is forbidden
# when its dotted import path equals one of these or starts with "<root>.".
_FORBIDDEN_ROOTS = frozenset({
    # LLM / AI inference
    "anthropic", "openai", "langchain", "langchain_core", "langchain_community",
    "cohere", "transformers", "llama_cpp", "llama_index", "llama-index",
    "ollama", "replicate", "huggingface_hub", "vertexai", "google.generativeai",
    # Network clients (a signal must not reach the network)
    "requests", "httpx", "urllib", "urllib3", "aiohttp", "socket",
    "websocket", "websockets",
})

_FROM_RE = re.compile(r"^\s*from\s+([.\w]+)\s+import\b")
_IMPORT_RE = re.compile(r"^\s*import\s+(.+)")


def _normalize(path: str) -> str:
    """Lower-noise path: backslashes → slashes (cross-platform matching)."""
    return path.replace("\\", "/")


def _is_signal_path(file_path: str) -> bool:
    norm = _normalize(file_path)
    return any(seg in norm for seg in _SIGNAL_PATH_SEGMENTS)


def _is_forbidden(module: str) -> bool:
    return any(module == root or module.startswith(root + ".") for root in _FORBIDDEN_ROOTS)


def forbidden_imports(text: str) -> list[str]:
    """Return the dotted module paths imported by ``text`` that are forbidden.

    Only actual import statements are inspected — comments and string literals
    that merely mention a module name are ignored. Order of first appearance is
    preserved; duplicates are collapsed.
    """
    found: list[str] = []
    for line in text.splitlines():
        modules: list[str] = []
        m = _FROM_RE.match(line)
        if m:
            modules.append(m.group(1))
        else:
            m = _IMPORT_RE.match(line)
            if m:
                # handle "import a, b as c, d.e"
                for part in m.group(1).split(","):
                    name = part.strip().split(" as ")[0].strip()
                    if name:
                        modules.append(name)
        for mod in modules:
            if _is_forbidden(mod) and mod not in found:
                found.append(mod)
    return found


def decide(data: dict) -> dict | None:
    """Return a PreToolUse deny payload, or None to allow.

    Denies when an Edit/Write targets the signal path and the *new* content
    introduces a forbidden import.
    """
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    if not _is_signal_path(file_path):
        return None

    # New content: Write uses `content`, Edit uses `new_string`.
    content = tool_input.get("content")
    if not isinstance(content, str):
        content = tool_input.get("new_string")
    if not isinstance(content, str) or not content:
        return None

    offenders = forbidden_imports(content)
    if not offenders:
        return None

    reason = (
        "CLAUDE.md Hard Constraint 4 — no LLM/AI-inference or network imports in "
        f"the signal path (src/signals/). This change introduces: {', '.join(offenders)}. "
        "Signals are deterministic math over local price_data / the SQLite DB. "
        "LLMs may be used for code/docs/analysis — never in the trade-decision loop."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


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
    out = decide(_read_input())
    if out is not None:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
