import hashlib
import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import OPENROUTER_API_KEY, get_db
from app.rag import build_system_prompt, chunk_source, complete_openrouter_sync, retrieve

router = APIRouter(tags=["public"])


def _verify(db: Session, raw_key: str) -> models.Agent:
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key")
    h = hashlib.sha256(raw_key.encode()).hexdigest()
    rec = db.query(models.ApiKey).filter(models.ApiKey.key_hash == h, models.ApiKey.revoked == False).first()  # noqa: E712
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid API key")
    agent = db.query(models.Agent).filter(models.Agent.id == rec.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/v1/chat")
def public_chat(
    body: schemas.ChatIn,
    db: Session = Depends(get_db),
    x_api_key: str = Header(default="", alias="x-api-key"),
):
    agent = _verify(db, x_api_key)
    business = db.query(models.Business).filter(models.Business.id == agent.business_id).first()
    bname = business.name if business else "the business"
    chunks, _ = retrieve(db, agent.id, body.message)
    system = build_system_prompt(agent, bname, chunks)
    sources = [chunk_source(c) for c in chunks]

    session_id = (body.session_id or "api").strip() or "api"
    conv = db.query(models.Conversation).filter(
        models.Conversation.agent_id == agent.id,
        models.Conversation.session_id == session_id,
    ).first()
    if not conv:
        conv = models.Conversation(agent_id=agent.id, session_id=session_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    db.add(models.Message(conversation_id=conv.id, role="user", content=body.message, sources=sources))
    db.commit()

    if not OPENROUTER_API_KEY:
        echo = "\n\n---\n\n".join((c.content or "")[:1000] for c in chunks) if chunks else "No relevant content found."
        db.add(models.Message(conversation_id=conv.id, role="assistant", content=echo, sources=sources))
        db.commit()
        return {"message": echo, "sources": sources, "model": "embed-only"}

    hist_rows = db.query(models.Message).filter(models.Message.conversation_id == conv.id).order_by(models.Message.created_at.desc()).limit(10).all()
    hist = [{"role": m.role, "content": m.content} for m in reversed(hist_rows) if m.role in ("user", "assistant")]
    try:
        answer = complete_openrouter_sync(agent.model, agent.temperature, system, hist, body.message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")
    db.add(models.Message(conversation_id=conv.id, role="assistant", content=answer, sources=sources))
    db.commit()
    return {"message": answer, "sources": sources, "model": agent.model}
