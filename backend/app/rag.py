"""Retrieval + prompt building + OpenRouter chat calls."""
import json
import math
from typing import AsyncGenerator, List

import httpx
from sqlalchemy.orm import Session

from app import models
from app.db import OPENROUTER_API_KEY, OPENROUTER_APP_NAME, OPENROUTER_SITE_URL, RETRIEVE_TOP_K
from app.ingest import embed_texts
from app.models import HAS_PGVECTOR


def cosine(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def retrieve(db: Session, agent_id: str, query: str, top_k: int = RETRIEVE_TOP_K):
    """Top-k chunks for agent via pgvector cosine, falling back to python cosine."""
    q_emb = embed_texts([query])[0]
    # Try pgvector ordering first.
    if HAS_PGVECTOR:
        try:
            rows = (
                db.query(models.Chunk)
                .filter(models.Chunk.agent_id == agent_id)
                .order_by(models.Chunk.embedding.cosine_distance(q_emb))  # type: ignore
                .limit(top_k)
                .all()
            )
            if rows:
                return rows, q_emb
        except Exception:
            pass
    # Fallback: load all agent chunks, score in python.
    all_rows = db.query(models.Chunk).filter(models.Chunk.agent_id == agent_id).all()
    scored = []
    for c in all_rows:
        emb = c.embedding
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                emb = None
        if not emb:
            continue
        try:
            scored.append((cosine(q_emb, list(emb)), c))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    # If embeddings missing entirely, fall back to keyword overlap so
    # embed-only mode still returns something useful.
    if not scored and all_rows:
        q = query.lower()
        terms = set(q.split())
        def overlap(c):
            t = (c.content or "").lower()
            return sum(1 for w in terms if w and w in t)
        all_rows.sort(key=overlap, reverse=True)
        return all_rows[:top_k], q_emb
    return [c for _, c in scored[:top_k]], q_emb


def build_system_prompt(agent: models.Agent, business_name: str, chunks) -> str:
    ctx = "\n\n---\n\n".join((c.content or "")[:2000] for c in chunks) if chunks else "No knowledge base content yet."
    return (
        f"You are '{agent.name}', a helpful business assistant for {business_name}.\n"
        f"Description: {agent.description or 'N/A'}\n"
        f"Business hours: {agent.business_hours or 'N/A'}\n"
        f"Contact: {agent.contact or 'N/A'}\n"
        f"Tone: {agent.tone or 'friendly'}. Be concise, accurate, and helpful.\n"
        f"Answer ONLY from the knowledge base context below when possible. "
        f"If the answer is not in the context, say you don't know and suggest contacting: {agent.contact or 'the business'}.\n\n"
        f"KNOWLEDGE BASE:\n{ctx}"
    )


def chat_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }


async def stream_openrouter(model: str, temperature: float, system: str, history: List[dict], user_msg: str) -> AsyncGenerator[str, None]:
    """Yield raw text deltas from OpenRouter SSE stream."""
    payload = {
        "model": model or "qwen/qwen3.8-27b:free",
        "temperature": temperature if temperature is not None else 0.7,
        "stream": True,
        "messages": [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_msg}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", "https://openrouter.ai/api/v1/chat/completions",
            headers=chat_headers(), json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue


def complete_openrouter_sync(model: str, temperature: float, system: str, history: List[dict], user_msg: str) -> str:
    payload = {
        "model": model or "qwen/qwen3.8-27b:free",
        "temperature": temperature if temperature is not None else 0.7,
        "stream": False,
        "messages": [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_msg}],
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=chat_headers(), json=payload,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
