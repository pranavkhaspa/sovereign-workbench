"""Bounded subprocess output and cancellation handling shared by sandbox drivers."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal

from sovereign_workbench.core.sandbox.base import SandboxResult


async def _read(stream: asyncio.StreamReader | None) -> bytes:
    result = bytearray()
    if stream is not None:
        while chunk := await stream.read(8192):
            result.extend(chunk[: max(0, 16_000 - len(result))])
    return bytes(result)


async def collect(process: asyncio.subprocess.Process, timeout: int) -> SandboxResult:
    readers = asyncio.gather(_read(process.stdout), _read(process.stderr))
    timed_out = False
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except TimeoutError:
        timed_out = True
    finally:
        with contextlib.suppress(ProcessLookupError):
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.returncode is None:
                process.kill()
        await process.wait()
        stdout, stderr = await readers
    return SandboxResult(
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", "replace"),
        stderr=stderr.decode("utf-8", "replace"),
        timed_out=timed_out,
    )
