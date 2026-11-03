from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    UUID,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    picture_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc))

    repositories: Mapped[list[Repository]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    indexing_jobs: Mapped[list[IndexingJob]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("user_id", "github_url", name="uq_repositories_user_github_url"),
        UniqueConstraint("id", "user_id", name="uq_repositories_id_user"),
        CheckConstraint(
            "indexing_status IN ('pending', 'queued', 'running', 'completed', 'failed')",
            name="ck_repositories_indexing_status",
        ),
        Index("ix_repositories_user_status", "user_id", "indexing_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    github_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(2048))
    indexing_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="repositories")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="repository", cascade="all, delete-orphan", overlaps="chat_sessions")
    indexing_jobs: Mapped[list[IndexingJob]] = relationship(back_populates="repository", cascade="all, delete-orphan", overlaps="indexing_jobs")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            ondelete="CASCADE",
            name="fk_chat_sessions_repository_owner",
        ),
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped[User] = relationship(back_populates="chat_sessions", overlaps="chat_sessions")
    repository: Mapped[Repository] = relationship(back_populates="chat_sessions", overlaps="chat_sessions,user")
    messages: Mapped[list[Message]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        Index("ix_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    evidence: Mapped[list[Evidence]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_message", "message_id"),
        Index("ix_evidence_file_path", "file_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(512))
    symbol_type: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(64))
    start_line: Mapped[int | None] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    reranker_score: Mapped[float | None] = mapped_column()
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    message: Mapped[Message] = relationship(back_populates="evidence")


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            ondelete="CASCADE",
            name="fk_indexing_jobs_repository_owner",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_indexing_jobs_status",
        ),
        Index("ix_indexing_jobs_user_status", "user_id", "status"),
        Index("ix_indexing_jobs_repository_created", "repository_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    current_stage: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user: Mapped[User] = relationship(back_populates="indexing_jobs", overlaps="indexing_jobs",)
    repository: Mapped[Repository] = relationship(back_populates="indexing_jobs",  overlaps="indexing_jobs,user")
