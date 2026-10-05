"""Text extraction + chunking + embedding via OpenRouter."""
import csv
import hashlib
import math
import os
from typing import List

import httpx

from app.db import OPENROUTER_API_KEY, OPENROUTER_EMBED_MODEL


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> List[str]:
    """Simple char splitter, no langchain dependency."""
    text = (text or "").strip()
    if not text:
        return []
    if size <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= size:
        overlap = size // 4
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = end - overlap
    return chunks


def extract_text_from_file(path: str, filename: str = "") -> str:
    ext = os.path.splitext(filename or path)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts).strip()
    if ext == ".docx":
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs).strip()
    if ext == ".csv":
        out = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            for row in csv.reader(f):
                out.append(" | ".join(row))
        return "\n".join(out).strip()
    # .txt / .md / anything else -> plain text
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def fallback_embedding(text: str, dims: int = 1536) -> List[float]:
    """Deterministic hash-bucketed embedding used when no OPENROUTER key is set."""
    vec = [0.0] * dims
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: List[str], dims: int = 1536) -> List[List[float]]:
    texts = [t or "" for t in texts]
    if not texts:
        return []
    if not OPENROUTER_API_KEY:
        return [fallback_embedding(t, dims) for t in texts]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    out: List[List[float]] = []
    # Batch in groups of 32 to stay under payload limits.
    for i in range(0, len(texts), 32):
        batch = texts[i:i + 32]
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers=headers,
                json={"model": OPENROUTER_EMBED_MODEL, "input": batch},
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("data", [])
            for item in items:
                emb = item.get("embedding", [])
                # Pad/truncate to dims for schema consistency.
                if len(emb) < dims:
                    emb = emb + [0.0] * (dims - len(emb))
                out.append(emb[:dims])
    if len(out) != len(texts):
        # Defensive: fill missing with fallback so chunk insert never breaks.
        while len(out) < len(texts):
            out.append(fallback_embedding(texts[len(out)], dims))
    return out
