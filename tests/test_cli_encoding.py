"""
Tests for CLI console-output encoding safety.

On a legacy Windows console (cp1252) any non-cp1252 glyph in console output
(✓, —, →, █) raises UnicodeEncodeError — which is what crashed `quant init`
after it had already initialized the DB. The CLI forces UTF-8 output at entry
so Rich glyphs never crash a command. This is a regression guard.
"""
from __future__ import annotations

import io
import sys

import pytest

from src.cli.encoding import force_utf8_output

_GLYPHS = "✓ — → █"  # checkmark, em-dash, arrow, block — none are cp1252


def test_cp1252_stream_rejects_glyphs_baseline() -> None:
    """Baseline: these glyphs genuinely cannot be written to a cp1252 stream."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")
    with pytest.raises(UnicodeEncodeError):
        stream.write(_GLYPHS)
        stream.flush()


def test_force_utf8_output_makes_cp1252_stream_unicode_safe() -> None:
    """After _force_utf8_output, writing non-cp1252 glyphs must not raise."""
    raw = io.BytesIO()
    cp1252_stream = io.TextIOWrapper(raw, encoding="cp1252", newline="")
    orig_out, orig_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = cp1252_stream
    try:
        force_utf8_output()
        sys.stdout.write(_GLYPHS)  # must not raise
        sys.stdout.flush()
    finally:
        sys.stdout, sys.stderr = orig_out, orig_err
    assert _GLYPHS.encode("utf-8") in raw.getvalue()


def test_force_utf8_output_noop_on_stream_without_reconfigure() -> None:
    """A stream lacking .reconfigure (e.g. a plain buffer) must be tolerated."""
    orig_out, orig_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()  # no .reconfigure attribute
    try:
        force_utf8_output()  # must not raise
    finally:
        sys.stdout, sys.stderr = orig_out, orig_err
