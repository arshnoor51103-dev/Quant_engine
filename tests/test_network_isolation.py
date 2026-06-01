"""
Infrastructure-layer network isolation guard (installed by conftest.py).

Mirrors the ``$QUANT_DB`` DB isolation: a test that forgets to mock yfinance /
requests / any HTTP transport and tries to reach the network must fail loudly,
not silently make a live call. Loopback stays allowed so a future in-process
server test (e.g. the dashboard) is not blocked.

These tests probe the guard directly through the socket layer.
"""
from __future__ import annotations

import socket

import pytest


def test_external_create_connection_is_blocked():
    """socket.create_connection to a non-loopback host raises the guard error."""
    with pytest.raises(RuntimeError, match="real network connection"):
        socket.create_connection(("example.com", 80), timeout=2)


def test_external_raw_socket_connect_is_blocked():
    """A raw socket.connect to a non-loopback host raises the guard error."""
    s = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="real network connection"):
            s.connect(("example.com", 80))
    finally:
        s.close()


def test_loopback_passes_the_guard():
    """Loopback is allowed: connecting to a free loopback port is refused by the
    OS (OSError), NOT intercepted by the guard (which would raise RuntimeError
    before the OS ever sees it)."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()

    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", free_port))
        # Raced onto the port and connected — still not a guard failure.
    except RuntimeError:
        pytest.fail("guard blocked loopback — loopback must be allowed")
    except OSError:
        pass  # expected: connection refused; the guard let it reach the OS
    finally:
        s.close()
