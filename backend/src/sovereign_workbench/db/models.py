from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sovereign_workbench.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    options: Mapped[str] = mapped_column(Text, default="{}")
    attachments: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    steps: Mapped[list[StepRow]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="StepRow.index"
    )
    artifacts: Mapped[list[ArtifactRow]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class StepRow(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    args: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[TaskRow] = relationship(back_populates="steps")


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(1024), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    chunks: Mapped[list[ChunkRow]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ChunkRow(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(24))
    path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    task: Mapped[TaskRow | None] = relationship(back_populates="artifacts")


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(64), default="system")
    detail: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
