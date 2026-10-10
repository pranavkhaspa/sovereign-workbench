"""Docker-backed sandbox for stronger isolation when Docker is available."""

from __future__ import annotations

import asyncio
import contextlib
import tempfile
from pathlib import Path
from uuid import uuid4

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.sandbox.base import Sandbox, SandboxResult
from sovereign_workbench.core.sandbox.process import collect


class DockerSandbox(Sandbox):
    """Run generated Python in a pre-pulled image with networking disabled."""

    def __init__(self, image: str | None = None) -> None:
        self.image = image or get_settings().sandbox_docker_image

    async def run(
        self, code: str, *, language: str = "python", timeout_s: int = 30
    ) -> SandboxResult:
        if language != "python":
            return SandboxResult(exit_code=2, stdout="", stderr=f"unsupported language: {language}")

        settings = get_settings()
        with tempfile.TemporaryDirectory(prefix="sw-docker-sandbox-") as tmp:
            workdir = Path(tmp)
            workdir.chmod(0o755)
            script = workdir / "main.py"
            script.write_text(code, encoding="utf-8")
            script.chmod(0o444)
            name = f"sw-sandbox-{uuid4().hex}"
            command = [
                "docker",
                "run",
                "--rm",
                "--pull=never",
                "--name",
                name,
                "--user",
                "65534:65534",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--log-driver=none",
                "--network=none",
                "--read-only",
                "--cpus",
                str(settings.sandbox_cpus),
                "--memory",
                f"{settings.sandbox_memory_mb}m",
                "--pids-limit",
                "64",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--mount",
                f"type=bind,src={workdir},dst=/workspace,readonly",
                self.image,
                "python",
                "-I",
                "/workspace/main.py",
            ]
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    start_new_session=True,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as exc:
                return SandboxResult(exit_code=127, stdout="", stderr=str(exc))

            try:
                return await collect(process, timeout_s)
            finally:
                with contextlib.suppress(OSError):
                    cleanup = await asyncio.create_subprocess_exec(
                        "docker",
                        "rm",
                        "--force",
                        name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,
                    )
                    await collect(cleanup, 10)
