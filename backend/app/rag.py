"""Retrieval + prompt building + OpenRouter chat calls."""
import json
import math
import re
from typing import AsyncGenerator, List

import httpx
from sqlalchemy.orm import Session

from app import models
from app.db import (
    MIN_SIMILARITY,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_SITE_URL,
    RETRIEVE_TOP_K,
    VECTOR_WEIGHT,
)
from app.ingest import embed_texts

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from",
    "had", "has", "have", "how", "i", "if", "in", "is", "it", "its", "me", "my",
    "of", "on", "or", "our", "that", "the", "their", "then", "there", "this",
    "to", "was", "we", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "you", "your",
}


def cosine(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _as_vector(raw) -> List[float] | None:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not raw:
        return None
    try:
        return [float(x) for x in raw]
    except Exception:
        return None


def _keyword_scores(query: str, rows) -> List[float]:
    """Small BM25 implementation over the agent's chunks."""
    terms = {t for t in re.findall(r"\w+", (query or "").lower()) if len(t) > 1 and t not in _STOPWORDS}
    if not terms or not rows:
        return [0.0] * len(rows)
    docs = [
        re.findall(r"\w+", f"{getattr(c, 'heading', '') or ''} {c.content or ''}".lower())
        for c in rows
    ]
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1.0
    df = {t: sum(1 for d in docs if t in d) for t in terms}
    k1, b = 1.5, 0.75
    scores = []
    for d in docs:
        dl = len(d) or 1
        score = 0.0
        for t in terms:
            tf = d.count(t)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
        scores.append(score)
    return scores


def retrieve(db: Session, agent_id: str, query: str, top_k: int = RETRIEVE_TOP_K):
    """Hybrid vector + BM25 top-k with a similarity floor.

    Chunks below MIN_SIMILARITY are only kept when they share query keywords.
    If nothing is relevant we return no context so the model can say it does
    not know instead of inventing an answer from unrelated text.
    """
    try:
        q_emb = embed_texts([query])[0]
    except Exception:
        # Embedding outage should degrade to keyword-only retrieval, not break chat.
        q_emb = []
    rows = db.query(models.Chunk).filter(models.Chunk.agent_id == agent_id).all()
    if not rows:
        return [], q_emb

    kw = _keyword_scores(query, rows)
    kw_max = max(kw) or 1.0
    scored = []
    for c, kw_score in zip(rows, kw):
        emb = _as_vector(c.embedding)
        vec = 0.0
        if emb:
            try:
                vec = max(0.0, cosine(q_emb, emb))
            except Exception:
                vec = 0.0
        if vec < MIN_SIMILARITY and kw_score <= 0:
            continue
        score = VECTOR_WEIGHT * vec + (1.0 - VECTOR_WEIGHT) * (kw_score / kw_max)
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]], q_emb


def source_label(index: int, chunk) -> str:
    label = f"[{index}]"
    url = getattr(chunk, "source_url", "") or ""
    heading = getattr(chunk, "heading", "") or ""
    if url:
        label += f" {url}"
    if heading:
        label += f" › {heading}"
    return label


def chunk_source(chunk) -> dict:
    url = getattr(chunk, "source_url", "") or ""
    heading = getattr(chunk, "heading", "") or ""
    content = (chunk.content or "")[:500]
    return {
        "document_id": chunk.document_id,
        "url": url,
        "title": heading or url or "source",
        "heading": heading,
        "snippet": content,
        "content": content,
    }


def build_system_prompt(agent: models.Agent, business_name: str, chunks) -> str:
    if chunks:
        ctx = "\n\n---\n\n".join(
            f"{source_label(i, c)}\n{(c.content or '')[:2000]}" for i, c in enumerate(chunks, 1)
        )
    else:
        ctx = "No knowledge base content found for this question."
    return (
        f"You are '{agent.name}', a helpful business assistant for {business_name}.\n"
        f"Description: {agent.description or 'N/A'}\n"
        f"Business hours: {agent.business_hours or 'N/A'}\n"
        f"Contact: {agent.contact or 'N/A'}\n"
        f"Tone: {agent.tone or 'friendly'}. Be concise, accurate, and helpful.\n"
        f"Answer ONLY from the knowledge base context below when possible. "
        f"If the answer is not in the context, say you don't know and suggest contacting: {agent.contact or 'the business'}.\n"
        f"When you use a source, cite its number like [1]. Never invent URLs.\n\n"
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
        "model": model or "google/gemma-4-31b-it:free",
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
        "model": model or "google/gemma-4-31b-it:free",
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
