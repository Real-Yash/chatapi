from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=list[schemas.BusinessOut])
def list_businesses(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Business)
        .filter(models.Business.owner_id == user.id)
        .order_by(models.Business.created_at.desc())
        .all()
    )


@router.post("", response_model=schemas.BusinessOut)
def create_business(
    body: schemas.BusinessIn, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    b = models.Business(owner_id=user.id, name=body.name.strip())
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.get("/{business_id}", response_model=schemas.BusinessOut)
def get_business(business_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(models.Business).filter(models.Business.id == business_id, models.Business.owner_id == user.id).first()
    if not b:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Business not found")
    return b


@router.put("/{business_id}", response_model=schemas.BusinessOut)
def update_business(
    business_id: str,
    body: schemas.BusinessIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    b = db.query(models.Business).filter(models.Business.id == business_id, models.Business.owner_id == user.id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Business not found")
    b.name = body.name.strip()
    db.commit()
    db.refresh(b)
    return b


@router.delete("/{business_id}")
def delete_business(business_id: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    b = db.query(models.Business).filter(models.Business.id == business_id, models.Business.owner_id == user.id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Business not found")
    db.delete(b)
    db.commit()
    return {"ok": True}
