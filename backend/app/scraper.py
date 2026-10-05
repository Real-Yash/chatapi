"""Same-domain BFS web scraper using requests + bs4."""
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def scrape_site(start_url: str, max_pages: int = 5):
    """BFS crawl same-domain pages. Returns list of {url, text}. max capped at 20."""
    max_pages = max(1, min(int(max_pages or 5), 20))
    seen = set()
    out = []
    q = deque([start_url])
    base_domain = _domain(start_url)
    headers = {"User-Agent": "ChatAPI/1.0 (+local)"}
    while q and len(out) < max_pages:
        url = q.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=headers, timeout=15)
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype and ctype:
                continue
            if r.status_code != 200:
                continue
            text = _clean_text(r.text)
            if text:
                out.append({"url": url, "text": text})
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                nxt = urljoin(url, a["href"]).split("#")[0]
                if _domain(nxt) == base_domain and nxt not in seen and nxt.startswith("http"):
                    q.append(nxt)
        except Exception:
            continue
    return out
