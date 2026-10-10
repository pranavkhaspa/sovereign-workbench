from __future__ import annotations

import asyncio

from sovereign_workbench.core.sandbox.subprocess_sandbox import SubprocessSandbox


def test_subprocess_sandbox_denies_socket_connects():
    code = """
import socket
try:
    socket.create_connection(("example.com", 443), timeout=1)
except OSError as error:
    print(error)
else:
    raise AssertionError("network connection unexpectedly succeeded")
"""
    result = asyncio.run(SubprocessSandbox().run(code))
    assert result.exit_code == 0
    assert "network disabled" in result.stdout
