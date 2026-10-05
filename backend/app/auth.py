from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models
from app.db import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET, get_db

_bearer = HTTPBearer(auto_error=False)


def _bcrypt():
    import bcrypt as _b
    return _b


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]
    return _bcrypt().hashpw(pw, _bcrypt().gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _bcrypt().checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(sub: str, expires_minutes: int = JWT_EXPIRE_MINUTES) -> str:
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode({"sub": sub, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_owned_business(db: Session, user_id: str, business_id: str) -> models.Business:
    b = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not b or b.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Business not found")
    return b


def get_owned_agent(db: Session, user_id: str, agent_id: str) -> models.Agent:
    a = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    b = db.query(models.Business).filter(models.Business.id == a.business_id).first()
    if not b or b.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a
