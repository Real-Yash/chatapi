import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import OPENROUTER_API_KEY, get_db
from app.rag import (
    build_system_prompt,
    chunk_source,
    fallback_answer,
    retrieve,
    stream_openrouter,
)

log = logging.getLogger("chatapi.chat")

router = APIRouter(tags=["chat"])


def _get_agent_by_slug(db: Session, slug: str) -> models.Agent:
    a = db.query(models.Agent).filter(models.Agent.slug == slug).first()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a


def _get_or_create_conversation(db: Session, agent_id: str, session_id: str) -> models.Conversation:
    session_id = (session_id or "default").strip() or "default"
    c = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.agent_id == agent_id,
            models.Conversation.session_id == session_id,
        )
        .first()
    )
    if not c:
        c = models.Conversation(agent_id=agent_id, session_id=session_id)
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def _history(db: Session, conv_id: str, limit: int = 10):
    msgs = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conv_id)
        .order_by(models.Message.created_at.desc())
        .limit(limit)
        .all()
    )
    msgs = list(reversed(msgs))
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


@router.post("/chat/{slug}")
async def chat(slug: str, body: schemas.ChatIn, db: Session = Depends(get_db)):
    agent = _get_agent_by_slug(db, slug)
    business = db.query(models.Business).filter(models.Business.id == agent.business_id).first()
    bname = business.name if business else "the business"

    chunks, _ = retrieve(db, agent.id, body.message)
    system = build_system_prompt(agent, bname, chunks)
    sources = [chunk_source(c) for c in chunks]
    conv = _get_or_create_conversation(db, agent.id, body.session_id or "default")
    hist = _history(db, conv.id)

    user_msg = models.Message(conversation_id=conv.id, role="user", content=body.message, sources=sources)
    db.add(user_msg)
    db.commit()

    # No OpenRouter key -> non-streaming fallback so the widget still works locally.
    if not OPENROUTER_API_KEY:
        echo = (
            (agent.welcome_message + "\n\n" if agent.welcome_message else "")
            + "I don't have a live LLM key configured, but here is what I found in the knowledge base:\n\n"
            + (
                "\n\n---\n\n".join((c.content or "")[:1000] for c in chunks)
                if chunks
                else "No relevant content found yet. Try adding documents first."
            )
        )
        db.add(models.Message(conversation_id=conv.id, role="assistant", content=echo, sources=sources))
        db.commit()

        async def fallback_gen():
            yield f"data: {json.dumps({'token': echo, 'content': echo, 'citations': sources, 'sources': sources, 'done': True})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(fallback_gen(), media_type="text/event-stream")

    async def gen():
        full = ""
        try:
            async for delta in stream_openrouter(agent.model, agent.temperature, system, hist, body.message):
                full += delta
                yield f"data: {json.dumps({'token': delta, 'content': delta, 'citations': sources, 'sources': sources, 'done': False})}\n\n"
        except Exception as e:  # noqa: BLE001
            log.warning("chat upstream unavailable for %s: %s", slug, e)
            err = fallback_answer(agent, chunks, body.message)
            full += err
            yield f"data: {json.dumps({'token': err, 'content': err, 'citations': sources, 'sources': sources, 'done': False})}\n\n"
        db.add(models.Message(conversation_id=conv.id, role="assistant", content=full, sources=sources))
        db.commit()
        yield f"data: {json.dumps({'token': '', 'content': '', 'citations': sources, 'sources': sources, 'done': True})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chat/{slug}/embed-only", response_model=schemas.EmbedOnlyOut)
def embed_only(slug: str, body: schemas.ChatIn, db: Session = Depends(get_db)):
    """Fallback when no OPENROUTER key: echo retrieved chunks without an LLM call."""
    agent = _get_agent_by_slug(db, slug)
    chunks, _ = retrieve(db, agent.id, body.message)
    data = [chunk_source(c) | {"content": c.content} for c in chunks]
    conv = _get_or_create_conversation(db, agent.id, body.session_id or "default")
    db.add(models.Message(conversation_id=conv.id, role="user", content=body.message, sources=data))
    echo = "\n\n---\n\n".join((c.content or "")[:1000] for c in chunks) if chunks else "No relevant content found."
    db.add(models.Message(conversation_id=conv.id, role="assistant", content=echo, sources=data))
    db.commit()
    return {"chunks": data, "message": echo}
