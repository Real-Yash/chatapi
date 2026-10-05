import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import UPLOAD_DIR, Base, engine, ensure_vector_extension
from app.routers import agents, analytics, auth, businesses, chat, compat, documents, keys, public

app = FastAPI(title="ChatAPI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ensure_vector_extension()
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(agents.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(public.router)
app.include_router(keys.router)
app.include_router(analytics.router)
app.include_router(compat.router)
