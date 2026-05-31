"""
Tests for the .claude/hooks/block_llm_in_signal_path.py PreToolUse hook.

Enforces CLAUDE.md Hard Constraint 4: no LLM/AI-inference or network imports
in the signal path (src/signals/). The hook is loaded by path because it lives
under .claude/hooks/, outside the normal package tree.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "block_llm_in_signal_path.py"
)


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_llm_in_signal_path", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_hook()


# ─── forbidden_imports: detection on import lines only ────────────────────────

class TestForbiddenImports:
    def test_detects_plain_llm_import(self) -> None:
        assert hook.forbidden_imports("import anthropic") == ["anthropic"]

    def test_detects_from_import(self) -> None:
        assert hook.forbidden_imports("from openai import OpenAI") == ["openai"]

    def test_detects_dotted_submodule(self) -> None:
        # google.generativeai is forbidden by its full path
        assert hook.forbidden_imports("import google.generativeai as genai") == [
            "google.generativeai"
        ]

    def test_detects_langchain_submodule_via_prefix(self) -> None:
        assert hook.forbidden_imports("from langchain.chains import LLMChain") == [
            "langchain.chains"
        ]

    def test_detects_network_client(self) -> None:
        assert hook.forbidden_imports("import requests") == ["requests"]

    def test_comma_import_list(self) -> None:
        roots = hook.forbidden_imports("import os, requests, sys")
        assert roots == ["requests"]

    def test_ignores_mentions_in_comments_and_strings(self) -> None:
        text = (
            "# this signal does NOT import openai or anthropic\n"
            "msg = 'we could use requests here but we do not'\n"
            "import numpy as np\n"
        )
        assert hook.forbidden_imports(text) == []

    def test_allows_legitimate_signal_imports(self) -> None:
        text = (
            "import numpy as np\n"
            "import pandas as pd\n"
            "from ..signals.base import Signal, SignalResult\n"
            "from sklearn.covariance import LedoitWolf\n"
        )
        assert hook.forbidden_imports(text) == []


# ─── decide: full PreToolUse contract ─────────────────────────────────────────

def _write(file_path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


def _edit(file_path: str, new_string: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": "x", "new_string": new_string},
    }


class TestDecide:
    def test_denies_write_with_llm_import_in_signals(self) -> None:
        out = hook.decide(_write("src/signals/sentiment.py", "import anthropic\n"))
        assert out is not None
        hso = out["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "anthropic" in hso["permissionDecisionReason"]

    def test_denies_edit_adding_llm_import_in_signals(self) -> None:
        out = hook.decide(_edit("src/signals/momentum.py", "from openai import OpenAI\n"))
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_denies_windows_path(self) -> None:
        out = hook.decide(_write(r"D:\Quant_engine\src\signals\foo.py", "import requests\n"))
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_allows_clean_signal_edit(self) -> None:
        assert hook.decide(_edit("src/signals/momentum.py", "import numpy as np\n")) is None

    def test_allows_llm_import_outside_signal_path(self) -> None:
        # ntfy / alerts legitimately use requests; only src/signals/ is guarded
        assert hook.decide(_write("src/alerts/ntfy.py", "import requests\n")) is None

    def test_allows_llm_import_in_optimizer(self) -> None:
        # portfolio construction is off the signal path
        assert hook.decide(_write("src/portfolio/optimizer.py", "import requests\n")) is None

    def test_no_file_path_is_allowed(self) -> None:
        assert hook.decide({"tool_name": "Write", "tool_input": {}}) is None

    def test_empty_input_is_allowed(self) -> None:
        assert hook.decide({}) is None
