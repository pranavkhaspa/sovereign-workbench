from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime

from sovereign_workbench.api.deps import get_task_runner
from sovereign_workbench.core.agent.runner import TaskRunner
from sovereign_workbench.db.models import TaskRow
from sovereign_workbench.db.session import session_scope
from sovereign_workbench.schemas.events import AgentEvent
from sovereign_workbench.schemas.tasks import TaskOptions


def test_disconnect_reconnect_and_restart_preserve_tokens(monkeypatch):
    async def scenario():
        runner = get_task_runner()
        release = asyncio.Event()
        calls = []

        async def fake_run(task_id, *args, **kwargs):
            calls.append(task_id)
            yield AgentEvent(
                type="token", task_id=task_id, at=datetime.now(UTC), data={"text": "first"}
            )
            await release.wait()
            yield AgentEvent(
                type="token", task_id=task_id, at=datetime.now(UTC), data={"text": "second"}
            )
            yield AgentEvent(
                type="done", task_id=task_id, at=datetime.now(UTC), data={"artifacts": []}
            )

        monkeypatch.setattr(runner.loop, "run", fake_run)
        task_id = runner.create_task("Summarize", model_id=None, options=TaskOptions())
        stream = runner.stream(task_id, "Summarize")
        first = await anext(stream)
        assert first.data["text"] == "first"
        await stream.aclose()
        release.set()
        remaining = [event async for event in runner.stream(task_id, "Summarize", after=first.id)]
        assert [event.type for event in remaining] == ["token", "done"]
        assert len(calls) == 1
        restarted = TaskRunner(runner.loop, runner.settings)
        replay = [event async for event in restarted.stream(task_id, "Summarize")]
        assert [event.data.get("text") for event in replay] == ["first", "second", None]
        assert len(calls) == 1
        assert not restarted._signals

    asyncio.run(scenario())


def test_running_task_cancels_without_waiting_for_model(monkeypatch):
    async def scenario():
        runner = get_task_runner()
        stopped = asyncio.Event()

        async def fake_run(task_id, *args, **kwargs):
            try:
                yield AgentEvent(type="step_start", task_id=task_id, at=datetime.now(UTC), data={})
                await asyncio.sleep(60)
            finally:
                stopped.set()

        monkeypatch.setattr(runner.loop, "run", fake_run)
        task_id = runner.create_task("Summarize", model_id=None, options=TaskOptions())
        stream = runner.stream(task_id, "Summarize")
        await anext(stream)
        assert runner.cancel_task(task_id)
        terminal = await asyncio.wait_for(anext(stream), timeout=2)
        assert terminal.data["code"] == "TASK_CANCELLED"
        assert stopped.is_set()
        await stream.aclose()
        with session_scope() as session:
            assert session.get(TaskRow, str(task_id)).status == "cancelled"

    asyncio.run(scenario())


def test_recovery_marks_crashed_runs_terminal():
    runner = get_task_runner()
    task_id = runner.create_task("Summarize", model_id=None, options=TaskOptions())
    runner._set_status(task_id, "running")
    runner.recover_interrupted()

    async def replay():
        return [event async for event in runner.stream(task_id, "Summarize")]

    events = asyncio.run(replay())
    assert events[-1].data["code"] == "TASK_INTERRUPTED"


def test_sse_header_cursor_and_task_pagination(client, monkeypatch):
    from test_completion import patch_plan

    patch_plan(monkeypatch, [{"title": "Answer", "kind": "answer"}])
    first = client.post("/api/tasks", json={"prompt": "First task"}).json()["id"]
    second = client.post("/api/tasks", json={"prompt": "Second task"}).json()["id"]
    assert client.get("/api/tasks", params={"limit": 1}).json()[0]["id"] == second
    older = client.get("/api/tasks", params={"cursor": second}).json()
    assert [task["id"] for task in older] == [first]
    stream = client.get(f"/api/tasks/{first}/events").text
    ids = re.findall(r"id: (\d+)\n", stream)
    resumed = client.get(f"/api/tasks/{first}/events", headers={"Last-Event-ID": ids[-2]})
    assert "event: done" in resumed.text
    assert "event: token" not in resumed.text
