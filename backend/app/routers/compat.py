"""Compatibility aliases so the Next.js frontend + widget work out of the box.

Frontend contract (frontend/lib/api.ts):
  POST /auth/signup, POST /auth/login, GET /auth/me
  GET|POST /agents, GET|PATCH|DELETE /agents/{id}
  GET /agents/{id}/knowledge, POST .../knowledge/text|file|url, DELETE .../knowledge/{kid}
  GET|POST /agents/{id}/api-keys, DELETE .../api-keys/{key}
  GET /public/agents/{slug}, POST /chat/{slug}, POST /agents/{id}/chat (playground)
Widget: GET /api/agents/{slug} (brand color)
"""
import json
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import create_access_token, get_current_user, get_owned_agent, hash_password
from app.db import UPLOAD_DIR, get_db
from app.routers.chat import _get_or_create_conversation, _history
from app.routers.documents import ALLOWED_EXTS, _store_chunks

router = APIRouter(tags=["compat"])


def _doc_to_knowledge(d: models.Document) -> dict:
    return {
        "id": d.id,
        "type": "text" if d.type == "manual" else ("file" if d.type == "upload" else "url"),
        "title": d.filename or d.source_url or d.id,
        "file_name": d.filename,
        "url": d.source_url,
        "content": "",
        "status": d.status if d.status in ("ready", "processing", "failed") else "ready",
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _public_agent(a: models.Agent) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "slug": a.slug,
        "welcome_message": a.welcome_message,
        "primary_color": a.primary_color,
        "primaryColor": a.primary_color,
        "tone": a.tone,
        "model": a.model,
        "description": a.description,
    }


# --- Auth aliases ---
@router.post("/auth/signup")
def signup_alias(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=body.email.lower().strip(), hashed_pw=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/auth/me")
def me_alias(user: models.User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}


# --- Agent PATCH alias ---
@router.patch("/agents/{agent_id}")
def patch_agent(agent_id: str, body: schemas.AgentUpdate, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_owned_agent(db, user.id, agent_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


# --- Knowledge aliases ---
@router.get("/agents/{agent_id}/knowledge")
def list_knowledge(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    docs = db.query(models.Document).filter(models.Document.agent_id == agent_id).order_by(models.Document.created_at.desc()).all()
    return [_doc_to_knowledge(d) for d in docs]


@router.post("/agents/{agent_id}/knowledge/text")
def add_knowledge_text(agent_id: str, body: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    text = (body.get("content") or body.get("text") or "").strip()
    title = body.get("title") or "manual"
    if not text:
        raise HTTPException(status_code=422, detail="content is required")
    doc = models.Document(agent_id=agent_id, type="manual", filename=title, source_url="", status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        _store_chunks(db, doc, text)
    except Exception as e:
        doc.status = "failed"
        doc.error = str(e)[:1000]
        db.commit()
    db.refresh(doc)
    return _doc_to_knowledge(doc)


@router.post("/agents/{agent_id}/knowledge/file")
async def add_knowledge_file(agent_id: str, file: UploadFile = File(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.ingest import extract_text_from_file
    get_owned_agent(db, user.id, agent_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {ext}")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, safe)
    data = await file.read()
    with open(dest, "wb") as f:
        f.write(data)
    doc = models.Document(agent_id=agent_id, type="upload", filename=file.filename or safe, source_url=dest, status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        _store_chunks(db, doc, extract_text_from_file(dest, file.filename or safe))
    except Exception as e:
        doc.status = "failed"
        doc.error = str(e)[:1000]
        db.commit()
    db.refresh(doc)
    return _doc_to_knowledge(doc)


@router.post("/agents/{agent_id}/knowledge/url")
def add_knowledge_url(agent_id: str, body: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.routers.documents import _store_chunks as _sc
    from app.scraper import scrape_site
    agent = get_owned_agent(db, user.id, agent_id)
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")
    context = f"{agent.name}. {agent.description or ''}".strip()
    pages = scrape_site(
        url,
        max_pages=body.get("max_pages"),
        keywords=body.get("keywords"),
        context=context,
    )
    if not pages:
        raise HTTPException(status_code=400, detail="No pages scraped")
    out = []
    for p in pages:
        doc = models.Document(agent_id=agent_id, type="scrape", filename=(p["url"] or "")[:255], source_url=p["url"], status="processing")
        db.add(doc)
        db.commit()
        db.refresh(doc)
        try:
            _sc(db, doc, p["text"])
        except Exception as e:
            doc.status = "failed"
            doc.error = str(e)[:1000]
            db.commit()
        db.refresh(doc)
        out.append(_doc_to_knowledge(doc))
    return out[0] if len(out) == 1 else out


@router.delete("/agents/{agent_id}/knowledge/{kid}")
def delete_knowledge(agent_id: str, kid: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    doc = db.query(models.Document).filter(models.Document.id == kid, models.Document.agent_id == agent_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    db.query(models.Chunk).filter(models.Chunk.document_id == doc.id).delete()
    db.delete(doc)
    db.commit()
    return {"ok": True}


# --- Public agent + widget brand color ---
@router.get("/public/agents/{slug}")
def public_agent(slug: str, db: Session = Depends(get_db)):
    a = db.query(models.Agent).filter(models.Agent.slug == slug).first()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _public_agent(a)


@router.get("/api/agents/{slug}")
def widget_agent(slug: str, db: Session = Depends(get_db)):
    a = db.query(models.Agent).filter(models.Agent.slug == slug).first()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _public_agent(a)


# --- Playground chat by agent id (authed) ---
@router.post("/agents/{agent_id}/chat")
async def playground_chat(agent_id: str, body: schemas.ChatIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.db import OPENROUTER_API_KEY
    from app.rag import build_system_prompt, chunk_source, retrieve, stream_openrouter
    a = get_owned_agent(db, user.id, agent_id)
    business = db.query(models.Business).filter(models.Business.id == a.business_id).first()
    bname = business.name if business else "the business"
    chunks, _ = retrieve(db, a.id, body.message)
    system = build_system_prompt(a, bname, chunks)
    sources = [chunk_source(c) for c in chunks]
    conv = _get_or_create_conversation(db, a.id, (body.session_id or "playground"))
    hist = _history(db, conv.id)
    db.add(models.Message(conversation_id=conv.id, role="user", content=body.message, sources=sources))
    db.commit()
    if not OPENROUTER_API_KEY:
        echo = "\n\n---\n\n".join((c.content or "")[:1000] for c in chunks) if chunks else "No relevant content found yet. Add knowledge first."
        db.add(models.Message(conversation_id=conv.id, role="assistant", content=echo, sources=sources))
        db.commit()

        async def fb():
            yield f"data: {json.dumps({'token': echo, 'content': echo, 'citations': sources, 'sources': sources, 'done': True})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(fb(), media_type="text/event-stream")

    async def gen():
        full = ""
        try:
            async for delta in stream_openrouter(a.model, a.temperature, system, hist, body.message):
                full += delta
                yield f"data: {json.dumps({'token': delta, 'content': delta, 'citations': sources, 'sources': sources, 'done': False})}\n\n"
        except Exception as e:
            full += f"\n[upstream error: {e}]"
            yield f"data: {json.dumps({'token': full, 'content': full, 'citations': sources, 'sources': sources, 'done': False})}\n\n"
        db.add(models.Message(conversation_id=conv.id, role="assistant", content=full, sources=sources))
        db.commit()
        yield f"data: {json.dumps({'token': '', 'content': '', 'citations': sources, 'sources': sources, 'done': True})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
