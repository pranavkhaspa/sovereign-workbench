"""Shared FastAPI dependencies: singletons for the agent stack."""

from __future__ import annotations

from functools import lru_cache

from sovereign_workbench.config import Settings, get_settings
from sovereign_workbench.core.agent.executor import StepExecutor
from sovereign_workbench.core.agent.loop import AgentLoop
from sovereign_workbench.core.agent.planner import TaskPlanner
from sovereign_workbench.core.agent.runner import TaskRunner
from sovereign_workbench.core.agent.tools.registry import ToolRegistry, build_default_registry
from sovereign_workbench.core.llm.registry import ModelRegistry, get_registry
from sovereign_workbench.core.llm.router import ModelRouter, get_router


@lru_cache
def get_tools() -> ToolRegistry:
    return build_default_registry()


@lru_cache
def _get_registry_and_router() -> tuple[ModelRegistry, ModelRouter]:
    return get_registry(), get_router()


@lru_cache
def get_task_runner() -> TaskRunner:
    registry, router = _get_registry_and_router()
    tools = get_tools()
    planner = TaskPlanner(registry, router, tools)
    executor = StepExecutor(tools)
    settings: Settings = get_settings()
    loop = AgentLoop(registry, router, planner, executor, settings)
    return TaskRunner(loop, settings)
