"""Subprocess sandbox.

Runs generated Python in a scratch directory with a stripped environment, a hard wall
clock and no network. This is process isolation, not a kernel jail — for hostile input
run the backend behind a container/VM (see docs/SOVEREIGNTY.md). It is enough to make
"run the code and verify it" safe for trusted-but-hallucinated model output.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.sandbox.base import Sandbox, SandboxResult
from sovereign_workbench.core.sandbox.process import collect
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
                    start_new_session=True,
                    preexec_fn=(
                        (lambda: _limit_process(memory_bytes, timeout_s))
                        if os.name == "posix"
                        else None
                    ),
                )
            except OSError as exc:
                return SandboxResult(exit_code=127, stdout="", stderr=str(exc))

            return await collect(proc, timeout_s)


def _limit_process(memory_bytes: int, timeout_s: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_s + 1, timeout_s + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


_sandbox: Sandbox | None = None


def get_sandbox() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        settings = get_settings()
        use_docker = settings.sandbox_backend == "docker" or (
            settings.sandbox_backend == "auto"
            and _docker_image_available(settings.sandbox_docker_image)
        )
        if use_docker:
            from sovereign_workbench.core.sandbox.docker_sandbox import DockerSandbox

            _sandbox = DockerSandbox()
        else:
            _sandbox = SubprocessSandbox()
    return _sandbox


def reset_sandbox() -> None:
    global _sandbox
    _sandbox = None


def _docker_image_available(image: str) -> bool:
    docker = shutil.which("docker")
    if docker is None:
        return False
    try:
        result = subprocess.run(
            [docker, "image", "inspect", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
