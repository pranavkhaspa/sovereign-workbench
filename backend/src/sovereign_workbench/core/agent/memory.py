"""Agent working memory: observations, citations and artifacts for one task."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMemory:
    prompt: str
    observations: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def add_observation(self, text: str) -> None:
        self.observations.append(text)

    def add_citations(self, citations: list[dict[str, Any]]) -> None:
        seen = {(str(c.get("document_id")), c.get("page"), c.get("span")) for c in self.citations}
        for cite in citations:
            key = (str(cite.get("document_id")), cite.get("page"), cite.get("span"))
            if key not in seen:
                self.citations.append(cite)
                seen.add(key)

    def add_artifact(self, artifact: dict[str, Any]) -> None:
        self.artifacts.append(artifact)

    def context_text(self, limit: int = 12_000) -> str:
        body = "\n\n".join(self.observations)
        return body[:limit]

    def summary(self) -> str:
        parts = [f"Task: {self.prompt}"]
        if self.citations:
            parts.append(f"Citations: {len(self.citations)}")
        if self.artifacts:
            names = ", ".join(a.get("filename", "?") for a in self.artifacts)
            parts.append(f"Artifacts: {names}")
        if self.observations:
            parts.append(self.context_text())
        return "\n".join(parts)
