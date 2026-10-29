from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Businesses ---
class BusinessIn(BaseModel):
    name: str = Field(min_length=1)


class BusinessOut(BaseModel):
    id: str
    owner_id: str
    name: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Agents ---
class AgentIn(BaseModel):
    business_id: Optional[str] = None
    name: str = Field(min_length=1)
    description: str = ""
    business_hours: str = ""
    contact: str = ""
    tone: str = "friendly"
    welcome_message: str = ""
    primary_color: str = "#4F46E5"
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    temperature: float = 0.7
    is_public: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    business_hours: Optional[str] = None
    contact: Optional[str] = None
    tone: Optional[str] = None
    welcome_message: Optional[str] = None
    primary_color: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    is_public: Optional[bool] = None


class AgentOut(BaseModel):
    id: str
    business_id: str
    slug: str
    name: str
    description: str = ""
    business_hours: str = ""
    contact: str = ""
    tone: str = "friendly"
    welcome_message: str = ""
    primary_color: str = "#4F46E5"
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    temperature: float = 0.7
    is_public: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Documents ---
class ManualDocIn(BaseModel):
    text: Optional[str] = None
    content: Optional[str] = None
    title: str = "manual"


class ScrapeIn(BaseModel):
    url: str = Field(min_length=4)
    max_pages: Optional[int] = None
    keywords: Optional[str] = None


class DocumentOut(BaseModel):
    id: str
    agent_id: str
    type: str
    source_url: str = ""
    filename: str = ""
    status: str
    error: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Chat ---
class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = "default"
    history: Optional[List[dict]] = None


class ApiKeyIn(BaseModel):
    name: Optional[str] = ""


class EmbedOnlyOut(BaseModel):
    chunks: List[dict]
    message: str = ""


# --- API keys ---
class ApiKeyCreateOut(BaseModel):
    id: str
    prefix: str
    key: str  # plaintext shown once


class ApiKeyOut(BaseModel):
    id: str
    agent_id: str
    prefix: str
    revoked: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Analytics ---
class AnalyticsOut(BaseModel):
    total_messages: int
    messages_per_day: List[dict]
    top_questions: List[dict]
