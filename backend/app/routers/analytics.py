from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_owned_agent
from app.db import get_db

router = APIRouter(prefix="/agents", tags=["analytics"])


@router.get("/{agent_id}/analytics", response_model=schemas.AnalyticsOut)
def analytics(agent_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_agent(db, user.id, agent_id)
    conv_ids = [c.id for c in db.query(models.Conversation).filter(models.Conversation.agent_id == agent_id).all()]
    total = 0
    per_day = {}
    questions = []
    if conv_ids:
        total = db.query(func.count(models.Message.id)).filter(
            models.Message.conversation_id.in_(conv_ids), models.Message.role == "user"
        ).scalar() or 0
        rows = db.query(models.Message).filter(
            models.Message.conversation_id.in_(conv_ids), models.Message.role == "user"
        ).order_by(models.Message.created_at.desc()).limit(500).all()
        for m in rows:
            day = m.created_at.date().isoformat() if m.created_at else "unknown"
            per_day[day] = per_day.get(day, 0) + 1
            if m.content:
                questions.append(m.content.strip()[:120])
    top = [{"question": q, "count": c} for q, c in Counter(questions).most_common(10)]
    days = [{"date": d, "count": per_day[d]} for d in sorted(per_day)]
    return {"total_messages": total, "messages_per_day": days, "top_questions": top}
