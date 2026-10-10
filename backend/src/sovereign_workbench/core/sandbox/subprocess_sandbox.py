"""Subprocess sandbox.

Runs generated Python in a scratch directory with a stripped environment, a hard wall
clock and no network. This is process isolation, not a kernel jail — for hostile input
run the backend behind a container/VM (see docs/SOVEREIGNTY.md). It is enough to make
"run the code and verify it" safe for trusted-but-hallucinated model output.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.sandbox.base import Sandbox, SandboxResult
from sovereign_workbench.observability.logging import get_logger

if os.name == "posix":
    import resource

log = get_logger(__name__)

_STRIPPED_ENV = {
    "PATH": "/usr/bin:/bin",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "NO_PROXY": "*",
    "no_proxy": "*",
}

_NO_NETWORK_RUNNER = (
    "import runpy, socket, sys; "
    "deny=lambda *a, **k: (_ for _ in ()).throw(OSError('sandbox network disabled')); "
    "socket.socket.connect=deny; socket.socket.connect_ex=deny; "
    "socket.socket.sendto=deny; "
    "setattr(socket.socket,'sendmsg',deny) if hasattr(socket.socket,'sendmsg') else None; "
    "socket.create_connection=deny; socket.getaddrinfo=deny; "
    "runpy.run_path(sys.argv[1], run_name='__main__')"
)


class SubprocessSandbox(Sandbox):
    def __init__(self, workdir: Path | None = None) -> None:
        self.workdir = workdir

    async def run(
        self, code: str, *, language: str = "python", timeout_s: int = 30
    ) -> SandboxResult:
        if language != "python":
            return SandboxResult(exit_code=2, stdout="", stderr=f"unsupported language: {language}")

        with tempfile.TemporaryDirectory(prefix="sw-sandbox-") as tmp:
            base = Path(self.workdir or tmp)
            script = base / "main.py"
            script.write_text(code, encoding="utf-8")
            env = dict(_STRIPPED_ENV)
            try:
                memory_bytes = get_settings().sandbox_memory_mb * 1024 * 1024
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    "-c",
                    _NO_NETWORK_RUNNER,
                    str(script),
                    cwd=str(base),
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    preexec_fn=(lambda: _limit_process(memory_bytes, timeout_s))
                    if os.name == "posix"
                    else None,
                )
            except OSError as exc:
                return SandboxResult(exit_code=127, stdout="", stderr=str(exc))

            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
                timed_out = False
            except TimeoutError:
                proc.kill()
                out, err = await proc.communicate()
                timed_out = True

            return SandboxResult(
                exit_code=proc.returncode if proc.returncode is not None else -1,
                stdout=out.decode("utf-8", "replace")[:16_000],
                stderr=err.decode("utf-8", "replace")[:16_000],
                timed_out=timed_out,
            )


def _limit_process(memory_bytes: int, timeout_s: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_s + 1, timeout_s + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))


_sandbox: Sandbox | None = None


def get_sandbox() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = SubprocessSandbox()
    return _sandbox


def reset_sandbox() -> None:
    global _sandbox
    _sandbox = None
