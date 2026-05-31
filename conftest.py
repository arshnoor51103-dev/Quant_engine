"""
Pytest session bootstrap — hard isolation from the live database.

Redirects every *default* DB access to a throwaway SQLite file via the F7
``$QUANT_DB`` override, BEFORE any test module imports ``src.data.storage``
(so the module-level ``DB_PATH = _default_db_path()`` resolves to the temp
path). This makes it impossible for a test that calls a CLI command function
on the default DB — e.g. ``recommend_command(save=True)`` reaching
``supersede_pending_recommendations`` — to ever touch ``data/quant.db``.

Tests that pass an explicit ``db_path=`` (the ``tmp_db`` fixture) are
unaffected; this only governs the default.
"""
import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="quant_test_")) / "quant_test.db"
os.environ["QUANT_DB"] = str(_TEST_DB)

# Import only AFTER the env var is set so DB_PATH binds to the throwaway path.
from src.data.storage import initialize  # noqa: E402

initialize()  # create schema at the throwaway path so default-DB calls work
