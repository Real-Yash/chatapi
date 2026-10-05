import hashlib
import json
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_owned_agent
from app.db import get_db

router = APIRouter(prefix="/agents", tags=["api-keys"])


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/{agent_id}/api-keys", response_model=schemas.ApiKeyCreateOut)
def create_key(agent_id: str, body: schemas.ApiKeyIn | None = None, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    raw = f"vu_{secrets.token_urlsafe(32)}"
    rec = models.ApiKey(agent_id=agent_id, key_hash=_hash(raw), prefix=raw[:10], revoked=False)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "prefix": rec.prefix, "key": raw}


@router.get("/{agent_id}/api-keys", response_model=list[schemas.ApiKeyOut])
def list_keys(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    return db.query(models.ApiKey).filter(models.ApiKey.agent_id == agent_id).order_by(models.ApiKey.created_at.desc()).all()


@router.delete("/{agent_id}/api-keys/{key_id}")
def revoke_key(agent_id: str, key_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    rec = db.query(models.ApiKey).filter(models.ApiKey.id == key_id, models.ApiKey.agent_id == agent_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Key not found")
    rec.revoked = True
    db.commit()
    return {"ok": True, "revoked": True}
