import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import EMBED_DIMS, Base


class _LocalVector(TypeDecorator):
    """JSON-backed embedding column for local SQLite storage."""

    impl = JSON
    cache_ok = True

    def __init__(self, dims: int = EMBED_DIMS):
        super().__init__()
        self.dims = dims


Vector = _LocalVector  # type: ignore
EmbeddingColumn = _LocalVector(EMBED_DIMS)  # type: ignore


def _uid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_pw: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    businesses: Mapped[list["Business"]] = relationship(
        "Business", back_populates="owner", cascade="all, delete-orphan"
    )


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner: Mapped["User"] = relationship("User", back_populates="businesses")
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="business", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(
        String, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    business_hours: Mapped[str] = mapped_column(String, default="", nullable=False)
    contact: Mapped[str] = mapped_column(String, default="", nullable=False)
    tone: Mapped[str] = mapped_column(String, default="friendly", nullable=False)
    welcome_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    primary_color: Mapped[str] = mapped_column(String, default="#4F46E5", nullable=False)
    model: Mapped[str] = mapped_column(String, default="nvidia/nemotron-3-ultra-550b-a55b:free", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="agents")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="agent", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="agent", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)  # manual | upload | scrape
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    filename: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="processing", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    heading: Mapped[str] = mapped_column(Text, default="", nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON works on both postgres & sqlite; JSONB preferred on pg but JSON is portable.
    sources: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
