"""Application configuration.

All settings come from environment variables (see `.env.example`). Nothing here
performs I/O beyond reading env + the model registry path.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

HardwareTier = Literal["min", "standard", "large"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "info"
    hardware_tier: HardwareTier = "min"

    # Sovereignty. When true, only loopback/private endpoints are reachable and
    # remote model providers are removed from the registry.
    airgap: bool = True

    # Local inference endpoints (loopback only).
    ollama_base_url: str = "http://127.0.0.1:11434"
    llamacpp_base_url: str = "http://127.0.0.1:8080"

    model_registry_path: Path = Path("./models/models.toml")

    # Retrieval.
    embedding_provider: Literal["hashing", "sentence-transformers"] = "hashing"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    chunk_size: int = Field(default=900, ge=128)
    chunk_overlap: int = Field(default=150, ge=0)

    # Optional cloud fallback (ignored when airgap is true).
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Storage.
    data_dir: Path = Path("./data")
    workspace_dir: Path = Path("./data/workspace")
    artifacts_dir: Path = Path("./data/artifacts")
    uploads_dir: Path = Path("./data/uploads")
    vector_store_dir: Path = Path("./data/vectorstore")
    database_url: str = "sqlite:///./data/workbench.sqlite3"

    # Agent limits (bounded for the small machine).
    max_agent_steps: int = Field(default=12, ge=1, le=100)
    tool_timeout_seconds: int = Field(default=120, ge=1)
    sandbox_memory_mb: int = Field(default=1024, ge=128)
    sandbox_cpus: float = Field(default=1.0, gt=0)
    sandbox_backend: Literal["auto", "docker", "subprocess"] = "auto"
    sandbox_docker_image: str = "python:3.12-slim"

    def ensure_dirs(self) -> None:
        """Create storage directories. Called at startup."""
        for path in (
            self.data_dir,
            self.workspace_dir,
            self.artifacts_dir,
            self.uploads_dir,
            self.vector_store_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
