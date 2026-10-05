import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.orm import relationship

from app.db import Base

# Local-only mode: always store embeddings as JSON lists in SQLite and score
# cosine similarity in Python. No pgvector / Postgres server required.
HAS_PGVECTOR = False


class _LocalVector(TypeDecorator):
    """JSON-backed embedding column for local SQLite storage."""
    impl = JSON
    cache_ok = True

    def __init__(self, dims=1536):
        super().__init__()
        self.dims = dims


Vector = _LocalVector  # type: ignore
EmbeddingColumn = _LocalVector(1536)  # type: ignore


def _uid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_pw = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    businesses = relationship("Business", back_populates="owner", cascade="all, delete-orphan")


class Business(Base):
    __tablename__ = "businesses"
    id = Column(String, primary_key=True, default=_uid)
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="businesses")
    agents = relationship("Agent", back_populates="business", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, default=_uid)
    business_id = Column(String, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="", nullable=False)
    business_hours = Column(String, default="", nullable=False)
    contact = Column(String, default="", nullable=False)
    tone = Column(String, default="friendly", nullable=False)
    welcome_message = Column(Text, default="", nullable=False)
    primary_color = Column(String, default="#4F46E5", nullable=False)
    model = Column(String, default="qwen/qwen3.8-27b:free", nullable=False)
    temperature = Column(Float, default=0.7, nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="agents")
    documents = relationship("Document", back_populates="agent", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uid)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)  # manual | upload | scrape
    source_url = Column(Text, default="", nullable=False)
    filename = Column(String, default="", nullable=False)
    status = Column(String, default="processing", nullable=False)  # processing | ready | failed
    error = Column(Text, default="", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True, default=_uid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(EmbeddingColumn, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uid)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    # JSON works on both postgres & sqlite; JSONB preferred on pg but JSON is portable.
    sources = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(String, primary_key=True, default=_uid)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    prefix = Column(String, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
