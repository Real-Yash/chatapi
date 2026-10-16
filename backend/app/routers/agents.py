from fastapi import APIRouter, Depends, HTTPException
from nanoid import generate
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_owned_agent
from app.db import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


def _slug_for(name: str) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in (name or "agent")).strip("-") or "agent"
    base = "-".join(base.split("-")[:4])[:30].strip("-") or "agent"
    return f"{base}-{generate(size=6)}"


@router.get("", response_model=list[schemas.AgentOut])
def list_agents(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    bids = [b.id for b in db.query(models.Business).filter(models.Business.owner_id == user.id).all()]
    if not bids:
        return []
    return db.query(models.Agent).filter(models.Agent.business_id.in_(bids)).order_by(models.Agent.created_at.desc()).all()


@router.post("", response_model=schemas.AgentOut)
def create_agent(body: schemas.AgentIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = None
    if body.business_id:
        b = db.query(models.Business).filter(models.Business.id == body.business_id, models.Business.owner_id == user.id).first()
    if not b:
        # Auto-create a default business so the frontend can create agents with just {name}.
        b = db.query(models.Business).filter(models.Business.owner_id == user.id).order_by(models.Business.created_at.asc()).first()
        if not b:
            b = models.Business(owner_id=user.id, name="My Business")
            db.add(b)
            db.commit()
            db.refresh(b)
    slug = _slug_for(body.name)
    while db.query(models.Agent).filter(models.Agent.slug == slug).first():
        slug = _slug_for(body.name)
    a = models.Agent(
        business_id=b.id, slug=slug, name=body.name.strip(),
        description=body.description or "", business_hours=body.business_hours or "",
        contact=body.contact or "", tone=body.tone or "friendly",
        welcome_message=body.welcome_message or "", primary_color=body.primary_color or "#4F46E5",
        model=body.model or "google/gemma-4-31b-it:free", temperature=body.temperature if body.temperature is not None else 0.7,
        is_public=body.is_public,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get("/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_owned_agent(db, user.id, agent_id)


@router.put("/{agent_id}", response_model=schemas.AgentOut)
def update_agent(agent_id: str, body: schemas.AgentUpdate, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_owned_agent(db, user.id, agent_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_owned_agent(db, user.id, agent_id)
    db.delete(a)
    db.commit()
    return {"ok": True}
