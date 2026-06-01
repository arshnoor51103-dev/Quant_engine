"""
Pytest session bootstrap — hard isolation from live resources (database + network).

1. **Database.** Redirects every *default* DB access to a throwaway SQLite file
   via the F7 ``$QUANT_DB`` override, BEFORE any test module imports
   ``src.data.storage`` (so the module-level ``DB_PATH = _default_db_path()``
   resolves to the temp path). This makes it impossible for a test that calls a
   CLI command function on the default DB — e.g. ``recommend_command(save=True)``
   reaching ``supersede_pending_recommendations`` — to ever touch
   ``data/quant.db``. Tests that pass an explicit ``db_path=`` (the ``tmp_db``
   fixture) are unaffected; this only governs the default.

2. **Network.** Installs a socket guard so any test attempting a real outbound
   (non-loopback) connection fails loudly instead of making a silent live call
   (a forgotten yfinance / requests mock). The network analog of the DB
   redirect — same lesson: isolation must be enforced at the infrastructure
   layer, not per-test discipline.
"""
import os
import socket
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.mkdtemp(prefix="quant_test_")) / "quant_test.db"
os.environ["QUANT_DB"] = str(_TEST_DB)

# Import only AFTER the env var is set so DB_PATH binds to the throwaway path.
from src.data.storage import initialize  # noqa: E402

initialize()  # create schema at the throwaway path so default-DB calls work


# ---------------------------------------------------------------------------
# Network isolation — close the *class*, not just the DB instance.
#
# The $QUANT_DB redirect above stops a test from touching the live DB. This is
# its network analog: a test that forgets to mock yfinance / requests / any HTTP
# transport and tries to reach the wire fails LOUDLY instead of making a silent
# live call. Enforced at the infrastructure layer so it cannot be forgotten
# per-test (the lesson from the 2026-05-31 conftest DB-isolation fix).
#
# Loopback (127.0.0.1 / ::1 / localhost) is allowed so a future in-process
# server test is not blocked. Mocked transports never reach a socket, so the
# existing suite is unaffected.
# ---------------------------------------------------------------------------
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

_real_create_connection = socket.create_connection
_real_socket_connect = socket.socket.connect
_real_socket_connect_ex = socket.socket.connect_ex


def _host_of(address: object) -> str | None:
    """Extract the host from a connect address; None for AF_UNIX paths (local)."""
    if isinstance(address, (tuple, list)) and len(address) >= 1:
        return str(address[0])
    return None


def _assert_local(address: object) -> None:
    host = _host_of(address)
    if host is not None and host not in _LOOPBACK_HOSTS:
        raise RuntimeError(
            f"Blocked a real network connection to {host!r} during tests. "
            f"Mock the transport (yfinance / requests / subprocess) instead — "
            f"see conftest.py network isolation."
        )


def _guard_create_connection(address, *args, **kwargs):
    _assert_local(address)
    return _real_create_connection(address, *args, **kwargs)


def _guard_socket_connect(self, address, *args, **kwargs):
    _assert_local(address)
    return _real_socket_connect(self, address, *args, **kwargs)


def _guard_socket_connect_ex(self, address, *args, **kwargs):
    _assert_local(address)
    return _real_socket_connect_ex(self, address, *args, **kwargs)


socket.create_connection = _guard_create_connection
socket.socket.connect = _guard_socket_connect
socket.socket.connect_ex = _guard_socket_connect_ex
