from __future__ import annotations

import os

import pytest

from sovereign_workbench.core.sandbox.docker_sandbox import DockerSandbox


@pytest.mark.skipif(os.environ.get("SW_TEST_DOCKER") != "1", reason="requires Docker-capable host")
@pytest.mark.asyncio
async def test_docker_execution_is_non_root_read_only_and_networkless():
    sandbox = DockerSandbox()
    result = await sandbox.run("""
import os, socket
assert os.getuid() == 65534
try:
    open('/workspace/injected.py', 'w')
except OSError:
    print('read-only source')
else:
    raise AssertionError('workspace was writable')
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
except OSError:
    print('network blocked')
else:
    raise AssertionError('network was reachable')
print(2 + 2)
""")
    assert result.exit_code == 0, result.stderr
    assert "read-only source" in result.stdout
    assert "network blocked" in result.stdout
    assert "4" in result.stdout
    timed = await sandbox.run("import time; time.sleep(20)", timeout_s=1)
    assert timed.timed_out
