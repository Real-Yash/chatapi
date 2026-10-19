import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    # Fully local default: SQLite file, no external DB server needed.
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_URL = f"sqlite:///{os.path.join(_BASE, 'chatapi.db')}"
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_EMBED_MODEL = os.getenv("OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-small")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:3000")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "ChatAPI")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"))

EMBED_DIMS = int(os.getenv("EMBED_DIMS", "1536"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
RETRIEVE_TOP_K = int(os.getenv("RETRIEVE_TOP_K", "8"))
# Minimum cosine similarity for a chunk to be considered relevant. Chunks below
# this floor are only kept if they match query keywords (hybrid retrieval), so
# out-of-domain questions return no context instead of hallucination bait.
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.25"))
# Weight of vector similarity vs. keyword (BM25) score in hybrid ranking.
VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.7"))

# --- Crawler ---
SCRAPE_MAX_PAGES = int(os.getenv("SCRAPE_MAX_PAGES", "25"))
SCRAPE_MAX_CANDIDATES = int(os.getenv("SCRAPE_MAX_CANDIDATES", "300"))
SCRAPE_CONCURRENCY = int(os.getenv("SCRAPE_CONCURRENCY", "6"))
SCRAPE_DELAY_MS = int(os.getenv("SCRAPE_DELAY_MS", "350"))
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "15"))
SCRAPE_LLM_RANK = os.getenv("SCRAPE_LLM_RANK", "1").lower() not in ("0", "false", "no")
SCRAPE_RANK_MODEL = os.getenv("SCRAPE_RANK_MODEL", "google/gemma-4-31b-it:free")
SCRAPE_MIN_TEXT_CHARS = int(os.getenv("SCRAPE_MIN_TEXT_CHARS", "200"))
SCRAPE_MIN_PAGE_CHARS = int(os.getenv("SCRAPE_MIN_PAGE_CHARS", "40"))
SCRAPE_JS_RENDER = os.getenv("SCRAPE_JS_RENDER", "1").lower() not in ("0", "false", "no")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_vector_extension():
    """Best-effort CREATE EXTENSION vector. No-op on SQLite (local-only mode)."""
    if DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    except Exception:
        pass


def ensure_schema():
    """Add columns introduced after the first release without a migration tool."""
    additions = {
        "source_url": "TEXT DEFAULT '' NOT NULL",
        "heading": "TEXT DEFAULT '' NOT NULL",
    }
    try:
        with engine.connect() as conn:
            if DATABASE_URL.startswith("sqlite"):
                existing = {row[1] for row in conn.execute(text("PRAGMA table_info(chunks)"))}
                for name, ddl in additions.items():
                    if name not in existing:
                        conn.execute(text(f"ALTER TABLE chunks ADD COLUMN {name} {ddl}"))
            else:
                for name, ddl in additions.items():
                    conn.execute(text(f"ALTER TABLE chunks ADD COLUMN IF NOT EXISTS {name} {ddl}"))
            conn.commit()
    except Exception:
        # Fresh databases already have the columns; never block startup.
        pass
