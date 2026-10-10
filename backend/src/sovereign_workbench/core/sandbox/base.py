from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class Sandbox(ABC):
    """Runs untrusted code with no network egress and a hard time limit."""

    @abstractmethod
    async def run(
        self, code: str, *, language: str = "python", timeout_s: int = 30
    ) -> SandboxResult: ...
