"""Sitemap-aware crawler with optional LLM URL ranking.

Discovery order: robots.txt -> sitemap(s) -> links on the seed page. Candidate
URLs are canonicalized, ranked against the agent's context (lexically, or by a
cheap LLM when a key is configured), then fetched concurrently with a global
politeness delay. HTML is reduced to main content (headings preserved as
`## ...`), PDFs are text-extracted, and thin pages can be retried through
headless Chromium if Playwright is installed.
"""
import gzip
import json
import logging
import os
import re
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from app.db import (
    OPENROUTER_API_KEY,
    SCRAPE_CONCURRENCY,
    SCRAPE_DELAY_MS,
    SCRAPE_JS_RENDER,
    SCRAPE_LLM_RANK,
    SCRAPE_MAX_CANDIDATES,
    SCRAPE_MAX_PAGES,
    SCRAPE_MIN_PAGE_CHARS,
    SCRAPE_MIN_TEXT_CHARS,
    SCRAPE_RANK_MODEL,
    SCRAPE_TIMEOUT,
)
from app.ingest import extract_text_from_file

log = logging.getLogger("chatapi.scraper")

USER_AGENT = "ChatAPI/1.0 (+local)"

_TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "ref", "referrer", "source", "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "utm_id", "_ga", "_gl",
}
_ASSET_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tif",
    ".tiff", ".css", ".js", ".mjs", ".json", ".xml", ".rss", ".atom", ".zip",
    ".rar", ".7z", ".tar", ".gz", ".mp3", ".mp4", ".mov", ".avi", ".webm",
    ".woff", ".woff2", ".ttf", ".eot", ".exe", ".dmg", ".apk",
}
_STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form", "iframe", "button"]
_HEADING_TAGS = {"h1", "h2", "h3", "h4"}
_BLOCK_TAGS = {"p", "li", "pre", "blockquote", "td", "th", "figcaption"}
_STOP_WORDS = {
    "the", "and", "for", "you", "your", "our", "with", "that", "this", "from",
    "are", "was", "were", "have", "has", "will", "can", "what", "when", "where",
    "how", "why", "who", "about", "into", "over", "under", "more", "most",
    "all", "any", "not", "but", "out", "use", "get", "set", "new", "one",
}


def _canonical(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        return ""
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    try:
        port = parsed.port
    except ValueError:
        return ""
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    query.sort()
    return urlunparse((scheme, netloc, path, "", urlencode(query), ""))


def _domain(url: str) -> str:
    return urlparse(_canonical(url)).netloc.lower()


def _same_site(url: str, base_domain: str) -> bool:
    host = _domain(url)
    return bool(host) and (host == base_domain or host.endswith("." + base_domain))


def _looks_binary(url: str) -> bool:
    return os.path.splitext(urlparse(url).path)[1].lower() in _ASSET_EXTS


class _RateLimiter:
    """Global minimum spacing between requests across worker threads."""

    def __init__(self, delay: float):
        self.delay = max(0.0, delay)
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        if not self.delay:
            return
        with self._lock:
            now = time.monotonic()
            sleep_for = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.delay
        if sleep_for:
            time.sleep(sleep_for)


_thread_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
        })
        _thread_local.session = session
    return session


def _request(url: str, timeout: int, attempts: int = 2):
    last_error = None
    for attempt in range(attempts):
        try:
            resp = _session().get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                time.sleep(0.8 * (attempt + 1))
                continue
            return resp
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    if last_error is not None:
        raise last_error
    return None


def _load_robots(start_url: str, timeout: int):
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    parser = RobotFileParser()
    parser.set_url(urljoin(base, "/robots.txt"))
    try:
        resp = _request(parser.url, timeout)
        if resp is not None and resp.status_code == 200:
            parser.parse(resp.text.splitlines())
            return parser
    except Exception:
        pass
    return None


def _is_html_response(resp) -> bool:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "html" in content_type or "text" in content_type:
        return True
    if not content_type or "octet-stream" in content_type:
        head = (resp.content or b"")[:512].lstrip().lower()
        return head.startswith(b"<!doctype") or head.startswith(b"<html")
    return False


def _allowed(robots, url: str) -> bool:
    if robots is None:
        return True
    try:
        return robots.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def _xml_locs(content: bytes):
    try:
        root = ET.fromstring(content)
    except Exception:
        return [], []
    root_tag = root.tag.split("}")[-1].lower()
    locs = [
        el.text.strip()
        for el in root.iter()
        if el.tag.split("}")[-1].lower() == "loc" and (el.text or "").strip()
    ]
    if root_tag == "sitemapindex":
        return [], locs
    return locs, []


def _read_sitemap(url: str, timeout: int, limit: int, depth: int = 0, seen=None, out=None, limiter=None):
    if out is None:
        out = []
    if seen is None:
        seen = set()
    if depth > 2 or url in seen or len(out) >= limit:
        return out
    seen.add(url)
    try:
        if limiter is not None:
            limiter.wait()
        resp = _request(url, timeout)
        if resp is None or resp.status_code != 200:
            return out
        content = resp.content
        if url.lower().endswith(".gz") or content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        urls, children = _xml_locs(content)
        for loc in urls:
            if len(out) >= limit:
                break
            loc = _canonical(urljoin(url, loc))
            if loc and loc not in out:
                out.append(loc)
        for child in children:
            if len(out) >= limit:
                break
            _read_sitemap(
                _canonical(urljoin(url, child)) or child,
                timeout, limit, depth + 1, seen, out, limiter,
            )
    except Exception as exc:
        log.info("sitemap read failed for %s: %s", url, exc)
    return out


def _extract_links(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = _canonical(urljoin(base_url, href))
        if not url:
            continue
        hint = " ".join(anchor.get_text(" ", strip=True).split())[:120]
        links.append({"url": url, "hint": hint})
    return links


def _html_to_text(html: str, url: str):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    root = soup.find("main") or soup.find("article") or soup.body or soup

    lines = []

    def walk(node):
        name = getattr(node, "name", None)
        if name in _HEADING_TAGS:
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                level = min(int(name[1]), 4)
                lines.append(f"\n{'#' * level} {text}\n")
            return
        if name in _BLOCK_TAGS:
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                lines.append(text)
            return
        for child in getattr(node, "children", []):
            if getattr(child, "name", None):
                walk(child)
            elif isinstance(child, str):
                text = " ".join(child.split())
                if text:
                    lines.append(text)

    walk(root)

    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if cleaned and cleaned[-1] == line:
            continue
        cleaned.append(line)
    return title, "\n".join(cleaned)


def _render_html(url: str, timeout: int) -> str:
    if not SCRAPE_JS_RENDER:
        return ""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        log.info("Playwright is not installed; cannot JS-render %s", url)
        return ""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                return page.content()
            finally:
                browser.close()
    except Exception as exc:
        log.warning("JS render failed for %s: %s", url, exc)
        return ""


def _pdf_text(content: bytes) -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        handle.write(content)
        handle.close()
        return extract_text_from_file(handle.name, "document.pdf")
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def _collect_candidates(start_url, robots, timeout, limit, prefetched, limiter):
    base_domain = _domain(start_url)
    found = []
    seen = set()

    def add(url, hint=""):
        url = _canonical(url)
        if not url or url in seen or not _same_site(url, base_domain):
            return
        if _looks_binary(url) and not urlparse(url).path.lower().endswith(".pdf"):
            return
        if not _allowed(robots, url):
            return
        seen.add(url)
        found.append({"url": url, "hint": hint})

    add(start_url, "seed")

    # Links on the seed page are the highest-signal candidates.
    limiter.wait()
    try:
        resp = _request(start_url, timeout)
        if resp is not None and resp.status_code == 200 and _is_html_response(resp):
            prefetched[start_url] = resp
            for link in _extract_links(resp.text, resp.url or start_url):
                if len(found) >= limit:
                    break
                add(link["url"], link["hint"])
    except Exception as exc:
        log.info("seed fetch failed for %s: %s", start_url, exc)

    sitemaps = []
    if robots is not None:
        try:
            sitemaps = list(robots.site_maps() or [])
        except Exception:
            sitemaps = []
    if not sitemaps:
        parsed = urlparse(start_url)
        sitemaps = [urljoin(f"{parsed.scheme}://{parsed.netloc}", "/sitemap.xml")]

    sitemap_urls = []
    for sitemap in sitemaps[:5]:
        if len(sitemap_urls) >= limit:
            break
        _read_sitemap(sitemap, timeout, limit - len(sitemap_urls), out=sitemap_urls, limiter=limiter)
    for url in sitemap_urls:
        if len(found) >= limit:
            break
        add(url, "sitemap")

    # SPA/JS-only sites expose no links in raw HTML; retry the seed once.
    if len(found) <= 1:
        rendered = _render_html(start_url, timeout)
        if rendered:
            for link in _extract_links(rendered, start_url):
                if len(found) >= limit:
                    break
                add(link["url"], link["hint"])

    return found[:limit]


def _lexical_rank(candidates, keywords, context):
    terms = {
        token
        for token in re.findall(r"\w+", f"{' '.join(keywords)} {context or ''}".lower())
        if len(token) > 2 and token not in _STOP_WORDS
    }

    def score(candidate):
        blob = f"{urlparse(candidate['url']).path} {candidate['hint']}".lower()
        value = sum(1 for term in terms if term in blob)
        if candidate["hint"] == "seed":
            value += 3
        return value

    ordered = sorted(candidates, key=score, reverse=True)
    seeds = [c for c in ordered if c["hint"] == "seed"]
    rest = [c for c in ordered if c["hint"] != "seed"]
    return seeds + rest


def _parse_json(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.S) or re.search(r"\[.*\]", raw, re.S)
    if not match:
        raise ValueError("no JSON in LLM response")
    return json.loads(match.group(0))


def _llm_rank(candidates, max_pages, keywords, context):
    if not OPENROUTER_API_KEY or not SCRAPE_LLM_RANK or not candidates:
        return []
    from app.rag import complete_openrouter_sync

    sample = candidates[:100]
    lines = []
    for candidate in sample:
        hint = candidate["hint"]
        suffix = f"  (link text: {hint})" if hint and hint not in ("seed", "sitemap") else ""
        lines.append(f"- {candidate['url']}{suffix}")

    system = (
        "You are a crawl planner for a business knowledge base. "
        "Pick the pages most likely to contain useful, unique business information "
        "(services, pricing, hours, FAQ, contact, policies, docs, about). "
        "Never invent URLs. Reply with JSON only."
    )
    user = (
        f"Business context:\n{context or 'N/A'}\n\n"
        f"Goal keywords: {', '.join(keywords) or 'general business information'}\n\n"
        f"Candidate URLs:\n{chr(10).join(lines)}\n\n"
        f"Select up to {max_pages} URLs. Avoid login, cart, search, tag, and pagination pages. "
        'Return: {"selected": [{"url": "<exact URL from the list>", "score": 0.0}]}'
    )
    try:
        raw = complete_openrouter_sync(SCRAPE_RANK_MODEL, 0.0, system, [], user)
        data = _parse_json(raw)
        items = data.get("selected") if isinstance(data, dict) else data
        allowed = {candidate["url"]: candidate for candidate in sample}
        selected = []
        seen = set()
        for item in items or []:
            url = item.get("url") if isinstance(item, dict) else item
            url = _canonical(str(url or ""))
            if url in allowed and url not in seen:
                seen.add(url)
                selected.append(allowed[url])
            if len(selected) >= max_pages:
                break
        return selected
    except Exception as exc:
        log.warning("LLM URL ranking failed, using lexical order: %s", exc)
        return []


def _llm_filter_pages(pages, keywords, context):
    if not OPENROUTER_API_KEY or not SCRAPE_LLM_RANK or len(pages) <= 1:
        return pages
    from app.rag import complete_openrouter_sync

    lines = []
    for page in pages:
        snippet = " ".join((page["text"] or "").split())[:400]
        lines.append(f"- {page['url']}\n  {snippet}")

    system = (
        "You curate a business knowledge base. Keep pages with useful, unique "
        "information for answering customer questions. Drop navigation, login, "
        "job listings, and duplicate boilerplate. Never invent URLs. Reply with JSON only."
    )
    user = (
        f"Business context:\n{context or 'N/A'}\n\n"
        f"Goal keywords: {', '.join(keywords) or 'general business information'}\n\n"
        f"Pages:\n{chr(10).join(lines)}\n\n"
        'Return: {"keep": ["<exact URL from the list>"]}'
    )
    try:
        raw = complete_openrouter_sync(SCRAPE_RANK_MODEL, 0.0, system, [], user)
        data = _parse_json(raw)
        keep = data.get("keep") if isinstance(data, dict) else data
        allowed = {page["url"] for page in pages}
        kept = {_canonical(str(url or "")) for url in (keep or [])}
        filtered = [page for page in pages if page["url"] in kept and page["url"] in allowed]
        return filtered or pages
    except Exception as exc:
        log.warning("LLM page filter failed, keeping all pages: %s", exc)
        return pages


def _crawl_one(candidate, robots, limiter, timeout, prefetched):
    url = candidate["url"]
    if not _allowed(robots, url):
        return None
    if _looks_binary(url) and not urlparse(url).path.lower().endswith(".pdf"):
        return None
    try:
        resp = prefetched.pop(url, None)
        if resp is None:
            limiter.wait()
            resp = _request(url, timeout)
    except Exception as exc:
        log.info("fetch failed for %s: %s", url, exc)
        return None
    if resp is None or resp.status_code != 200:
        return None

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "pdf" in content_type or urlparse(url).path.lower().endswith(".pdf"):
        title = os.path.basename(urlparse(url).path) or url
        text = _pdf_text(resp.content)
    else:
        if not _is_html_response(resp):
            return None
        title, text = _html_to_text(resp.text, url)
        if len(re.sub(r"\s+", "", text)) < SCRAPE_MIN_TEXT_CHARS:
            rendered = _render_html(url, timeout)
            if rendered:
                rendered_title, rendered_text = _html_to_text(rendered, url)
                if len(rendered_text) > len(text):
                    title, text = rendered_title, rendered_text

    text = (text or "").strip()
    if len(re.sub(r"\s+", "", text)) < SCRAPE_MIN_PAGE_CHARS:
        return None
    return {"url": url, "title": title or url, "text": text}


def scrape_site(start_url: str, max_pages: int = None, keywords=None, context: str = ""):
    """Discover, rank, and crawl a site.

    Returns a list of `{url, title, text}` preserving the selected URL order.
    Set `keywords` (list or comma/newline separated string) to steer ranking;
    `context` is free text about the business (agent name/description).
    """
    start_url = _canonical(start_url)
    if not start_url:
        return []

    max_pages = max(1, min(int(max_pages or SCRAPE_MAX_PAGES), 100))
    if isinstance(keywords, str):
        keywords = [k.strip() for k in re.split(r"[,\n]", keywords) if k.strip()]
    keywords = [str(k) for k in (keywords or []) if k]
    if not keywords and context:
        keywords = list(dict.fromkeys(
            token
            for token in re.findall(r"\w+", context.lower())
            if len(token) > 2 and token not in _STOP_WORDS
        ))[:12]

    timeout = SCRAPE_TIMEOUT
    robots = _load_robots(start_url, timeout)

    delay = SCRAPE_DELAY_MS / 1000.0
    if robots is not None:
        try:
            crawl_delay = robots.crawl_delay(USER_AGENT) or robots.crawl_delay("*")
            if crawl_delay:
                delay = max(delay, float(crawl_delay))
        except Exception:
            pass

    limiter = _RateLimiter(delay)
    prefetched = {}
    candidates = _collect_candidates(
        start_url, robots, timeout, SCRAPE_MAX_CANDIDATES, prefetched, limiter
    )
    if not candidates:
        return []

    ranked = _lexical_rank(candidates, keywords, context)
    if len(candidates) <= max_pages:
        selected = ranked
    else:
        selected = _llm_rank(ranked, max_pages, keywords, context) or ranked[:max_pages]
    seed = next((c for c in candidates if c["url"] == start_url), None)
    if seed is not None and all(c["url"] != start_url for c in selected):
        selected = [seed] + selected
    selected = selected[:max_pages]

    pages_by_url = {}
    workers = max(1, min(SCRAPE_CONCURRENCY, len(selected)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_crawl_one, candidate, robots, limiter, timeout, prefetched): candidate
            for candidate in selected
        }
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                page = future.result()
            except Exception as exc:
                log.warning("crawl failed for %s: %s", candidate["url"], exc)
                page = None
            if page:
                pages_by_url[candidate["url"]] = page

    pages = [pages_by_url[c["url"]] for c in selected if c["url"] in pages_by_url]
    return _llm_filter_pages(pages, keywords, context)
