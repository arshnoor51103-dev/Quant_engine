"""
Console output encoding safety.

Python < 3.15 on Windows defaults interactive console output to the active code
page (typically cp1252), so a non-cp1252 glyph in a printed string (the init
checkmark, em-dashes, arrows, box-drawing) raises UnicodeEncodeError mid-command
— after side effects have already run, and even while printing a crash
traceback. This module forces UTF-8 output at process entry.

Shared by the interactive CLI (``main.py``) and the scheduled entry
(``scripts/daily_run.py``) so neither path can crash on a glyph (F5).
"""
from __future__ import annotations

import sys


def force_utf8_output() -> None:
    """Reconfigure stdout/stderr to UTF-8 so console output never crashes.

    No-op on streams that cannot be reconfigured (e.g. some captured test
    buffers, or a stream already written to).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            # Already written to, or not reconfigurable — leave as-is.
            pass
