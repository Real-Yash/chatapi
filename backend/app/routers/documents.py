import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_owned_agent
from app.db import CHUNK_OVERLAP, CHUNK_SIZE, UPLOAD_DIR, get_db
from app.ingest import chunk_sections, embed_texts, extract_text_from_file

router = APIRouter(tags=["documents"])

ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".csv", ".md"}


def _store_chunks(db: Session, doc: models.Document, text: str):
    chunks = chunk_sections(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        doc.status = "failed"
        doc.error = "No extractable text found"
        db.commit()
        return []
    embeddings = embed_texts([f"{c['heading']}\n{c['content']}" if c["heading"] else c["content"] for c in chunks])
    source_url = doc.source_url or ""
    if not source_url.startswith(("http://", "https://")):
        # Uploaded files store a local path; never expose it as a citation URL.
        source_url = ""
    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append(
            models.Chunk(
                document_id=doc.id,
                agent_id=doc.agent_id,
                content=chunk["content"],
                heading=chunk["heading"],
                source_url=source_url,
                embedding=emb,
            )
        )
    db.bulk_save_objects(rows)
    doc.status = "ready"
    doc.error = ""
    db.commit()
    return rows


@router.post("/agents/{agent_id}/documents/manual", response_model=schemas.DocumentOut)
def add_manual(
    agent_id: str,
    body: schemas.ManualDocIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_agent(db, user.id, agent_id)
    text = (body.text or body.content or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text or content is required")
    doc = models.Document(
        agent_id=agent_id, type="manual", filename=body.title or "manual", source_url="", status="processing"
    )
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
    return doc


@router.post("/agents/{agent_id}/documents/upload", response_model=schemas.DocumentOut)
async def upload_doc(
    agent_id: str,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_agent(db, user.id, agent_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED_EXTS)}")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, safe)
    data = await file.read()
    with open(dest, "wb") as f:
        f.write(data)
    doc = models.Document(
        agent_id=agent_id, type="upload", filename=file.filename or safe, source_url=dest, status="processing"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        text = extract_text_from_file(dest, file.filename or safe)
        _store_chunks(db, doc, text)
    except Exception as e:
        doc.status = "failed"
        doc.error = str(e)[:1000]
        db.commit()
    db.refresh(doc)
    return doc


@router.post("/agents/{agent_id}/documents/scrape", response_model=list[schemas.DocumentOut])
def scrape_docs(
    agent_id: str, body: schemas.ScrapeIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from app.scraper import scrape_site

    agent = get_owned_agent(db, user.id, agent_id)
    context = f"{agent.name}. {agent.description or ''}".strip()
    pages = scrape_site(body.url, max_pages=body.max_pages, keywords=body.keywords, context=context)
    if not pages:
        raise HTTPException(status_code=400, detail="No pages scraped")
    created = []
    for p in pages:
        doc = models.Document(
            agent_id=agent_id, type="scrape", filename=(p["url"] or "")[:255], source_url=p["url"], status="processing"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        try:
            _store_chunks(db, doc, p["text"])
        except Exception as e:
            doc.status = "failed"
            doc.error = str(e)[:1000]
            db.commit()
        db.refresh(doc)
        created.append(doc)
    return created


@router.get("/agents/{agent_id}/documents", response_model=list[schemas.DocumentOut])
def list_docs(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    return (
        db.query(models.Document)
        .filter(models.Document.agent_id == agent_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.delete("/documents/{doc_id}")
def delete_doc(doc_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    get_owned_agent(db, user.id, doc.agent_id)
    db.query(models.Chunk).filter(models.Chunk.document_id == doc.id).delete()
    db.delete(doc)
    db.commit()
    return {"ok": True}
