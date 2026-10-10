from __future__ import annotations

import json

from sovereign_workbench.core.llm.provider import Completion


def test_agent_recovers_once_and_keeps_total_step_limit(client, monkeypatch):
    calls = []

    async def plan(*args, **kwargs):
        calls.append(args[2][-1].content)
        tool = "missing_tool" if len(calls) == 1 else "calculate"
        return Completion(
            model_id=args[1].id,
            text=json.dumps(
                {"steps": [{"title": "Compute", "tool": tool, "args": {"expression": "3 * 7"}}]}
            ),
        )

    async def answer(*args, **kwargs):
        yield "21"

    monkeypatch.setattr("sovereign_workbench.core.agent.planner.run_chat", plan)
    monkeypatch.setattr("sovereign_workbench.core.agent.loop.run_stream", answer)
    response = client.post("/api/chat", json={"prompt": "Compute three times seven"})
    assert '"replanned": true' in response.text
    assert "event: done" in response.text
    assert "unknown tool" in calls[1]
    assert len(calls) == 2

    async def long_plan(*args, **kwargs):
        return Completion(
            model_id=args[1].id,
            text=json.dumps(
                {
                    "steps": [
                        {"title": "Compute", "tool": "calculate", "args": {"expression": "3 * 7"}},
                        {"title": "Continue", "tool": "calculate", "args": {"expression": "4 * 7"}},
                    ]
                }
            ),
        )

    monkeypatch.setattr("sovereign_workbench.core.agent.planner.run_chat", long_plan)
    response = client.post("/api/chat", json={"prompt": "Compute", "options": {"max_steps": 1}})
    assert "STEP_LIMIT" in response.text
    assert "event: done" not in response.text


def test_cited_search_survives_event_serialization(client, monkeypatch):
    from test_completion import patch_plan

    client.post(
        "/api/documents", files={"file": ("sop.txt", b"Valve corrosion requires inspection.")}
    )
    patch_plan(
        monkeypatch,
        [{"title": "Search", "tool": "search_documents", "args": {"query": "valve corrosion"}}],
    )
    result = client.post("/api/chat", json={"prompt": "Search the manual"})
    assert "event: done" in result.text
    assert '"citations": [{' in result.text
    assert '"filename": "sop.txt"' in result.text
