"""Retrieval + prompt building + OpenRouter chat calls."""

import asyncio
import json
import logging
import math
import os
import re
import time
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

log = logging.getLogger("chatapi.rag")

DEFAULT_CHAT_MODEL = os.getenv("OPENROUTER_CHAT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "nvidia/nemotron-3-ultra-550b-a55b:free,"
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,"
        "google/gemma-4-31b-it:free,"
        "dots-studio/dots-3-note-preview:free",
    ).split(",")
    if m.strip()
]
RETRY_ATTEMPTS = max(1, int(os.getenv("OPENROUTER_RETRIES", "2")))
RETRY_STATUS = {429, 500, 502, 503, 504}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "then",
    "there",
    "this",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "you",
    "your",
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
    docs = [re.findall(r"\w+", f"{getattr(c, 'heading', '') or ''} {c.content or ''}".lower()) for c in rows]
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
        ctx = "\n\n---\n\n".join(f"{source_label(i, c)}\n{(c.content or '')[:2000]}" for i, c in enumerate(chunks, 1))
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


def model_chain(model: str) -> List[str]:
    """Requested model first, then configured fallbacks, de-duplicated."""
    chain: List[str] = []
    for m in [model or DEFAULT_CHAT_MODEL, *FALLBACK_MODELS]:
        if m and m not in chain:
            chain.append(m)
    return chain


def _status_code(exc: Exception) -> int | None:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    return None


def _retryable(exc: Exception) -> bool:
    code = _status_code(exc)
    return code is None or code in RETRY_STATUS


async def _stream_model(
    model: str, temperature: float, system: str, history: List[dict], user_msg: str
) -> AsyncGenerator[str, None]:
    payload = {
        "model": model,
        "temperature": temperature if temperature is not None else 0.7,
        "stream": True,
        "messages": [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_msg}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            headers=chat_headers(),
            json=payload,
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


async def stream_openrouter(
    model: str, temperature: float, system: str, history: List[dict], user_msg: str
) -> AsyncGenerator[str, None]:
    """Stream a reply, retrying rate-limited models and falling back down a chain.

    Free OpenRouter models are frequently rate-limited upstream (HTTP 429). We
    retry the same model briefly, then move to the next configured fallback.
    If a model has already produced tokens we keep the partial reply rather than
    duplicating text.
    """
    last_err: Exception | None = None
    for candidate in model_chain(model):
        for attempt in range(RETRY_ATTEMPTS):
            produced = False
            try:
                async for delta in _stream_model(candidate, temperature, system, history, user_msg):
                    produced = True
                    yield delta
                return
            except Exception as exc:  # noqa: BLE001 - reported to caller after chain
                last_err = exc
                if produced:
                    log.warning("model %s failed after partial output: %s", candidate, exc)
                    return
                retryable = _retryable(exc)
                log.warning(
                    "model %s attempt %d/%d failed (%s): %s",
                    candidate,
                    attempt + 1,
                    RETRY_ATTEMPTS,
                    _status_code(exc) or type(exc).__name__,
                    exc,
                )
                if not retryable:
                    break
                if attempt + 1 < RETRY_ATTEMPTS:
                    await asyncio.sleep(1.2 * (attempt + 1))
    if last_err:
        raise last_err


def complete_openrouter_sync(model: str, temperature: float, system: str, history: List[dict], user_msg: str) -> str:
    last_err: Exception | None = None
    for candidate in model_chain(model):
        for attempt in range(RETRY_ATTEMPTS):
            payload = {
                "model": candidate,
                "temperature": temperature if temperature is not None else 0.7,
                "stream": False,
                "messages": [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_msg}],
            }
            try:
                with httpx.Client(timeout=120) as client:
                    r = client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=chat_headers(),
                        json=payload,
                    )
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                log.warning(
                    "completion model %s attempt %d/%d failed (%s): %s",
                    candidate,
                    attempt + 1,
                    RETRY_ATTEMPTS,
                    _status_code(exc) or type(exc).__name__,
                    exc,
                )
                if not _retryable(exc):
                    break
                if attempt + 1 < RETRY_ATTEMPTS:
                    time.sleep(1.2 * (attempt + 1))
    if last_err:
        raise last_err
    return ""


def fallback_answer(agent: models.Agent, chunks, message: str = "") -> str:
    """Grounded reply used when every upstream model is unavailable.

    Keeps the demo useful instead of surfacing a 429/502 to the visitor.
    """
    contact = agent.contact or "the team"
    usable = [c for c in (chunks or []) if (getattr(c, "content", "") or "").strip()]
    if not usable:
        return (
            "I'm having trouble reaching the live AI service right now. "
            f"Please try again in a moment, or contact {contact}."
        )
    parts = []
    for chunk in usable[:2]:
        body = (chunk.content or "").strip()
        if len(body) > 700:
            body = body[:700].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
        parts.append(body)
    return (
        "Here's what I found in our knowledge base:\n\n"
        + "\n\n".join(parts)
        + f"\n\nFor anything else, contact {contact}."
    )
