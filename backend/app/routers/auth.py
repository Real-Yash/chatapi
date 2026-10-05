from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import get_db

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=schemas.TokenOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=body.email.lower().strip(), hashed_pw=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post("/auth/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
