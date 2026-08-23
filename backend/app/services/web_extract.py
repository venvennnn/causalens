from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.gdelt.scoring import is_aggregator, is_likely_article_page
from app.logging import log

SCRIPT_RE = re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.IGNORECASE)
STYLE_RE = re.compile(r"<style\b[^>]*>[\s\S]*?</style>", re.IGNORECASE)
NOSCRIPT_RE = re.compile(r"<noscript\b[^>]*>[\s\S]*?</noscript>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
TITLE_RE = re.compile(r"<title[^>]*>([\s\S]*?)</title>", re.IGNORECASE)
OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_TITLE_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    re.IGNORECASE,
)
P_RE = re.compile(r"<p\b[^>]*>([\s\S]*?)</p>", re.IGNORECASE)
ARTICLE_RE = re.compile(r"<article\b[^>]*>([\s\S]*?)</article>", re.IGNORECASE)
JSONLD_BODY_RE = re.compile(r'"articleBody"\s*:\s*"((?:\\.|[^"\\])*)"')
SKIP_SCHEMES = {"javascript", "data", "file", "about"}
SKIP_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".zip", ".xml", ".rss")


@dataclass
class ExtractedPage:
    title: str
    body: str
    published: str | None = None


def _visible_text(chunk: str) -> str:
    text = html_lib.unescape(TAG_RE.sub(" ", chunk or ""))
    text = WS_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_from_html(html: str, fallback_title: str = "") -> ExtractedPage:
    raw = html or ""
    cleaned = SCRIPT_RE.sub(" ", raw)
    cleaned = STYLE_RE.sub(" ", cleaned)
    cleaned = NOSCRIPT_RE.sub(" ", cleaned)

    title = ""
    og = OG_TITLE_RE.search(raw) or OG_TITLE_RE_ALT.search(raw)
    if og:
        title = html_lib.unescape(og.group(1)).strip()
    if not title:
        match = TITLE_RE.search(raw)
        if match:
            title = _visible_text(match.group(1)).split("|")[0].split(" - ")[0].strip()
    title = title or fallback_title

    body = ""
    jsonld = JSONLD_BODY_RE.search(raw)
    if jsonld:
        body = _visible_text(
            jsonld.group(1).replace("\\n", "\n").replace("\\r", " ").replace('\\"', '"')
        )

    if len(body) < 250:
        article_chunks = ARTICLE_RE.findall(cleaned)
        paragraphs = []
        source = article_chunks[0] if article_chunks else cleaned
        paragraphs = [_visible_text(item) for item in P_RE.findall(source)]
        paragraphs = [item for item in paragraphs if len(item) >= 40]
        body = "\n\n".join(paragraphs)

    if len(body) < 250:
        body = _visible_text(cleaned)

    return ExtractedPage(title=title, body=body[:20000], published=None)


def should_fetch_candidate(url: str, title: str, raw: dict | None = None) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not parsed.scheme.startswith("http") or parsed.scheme in SKIP_SCHEMES or not host:
        return False
    if any((parsed.path or "").lower().endswith(suffix) for suffix in SKIP_SUFFIXES):
        return False
    if is_aggregator(url, host):
        return False
    if raw and raw.get("is_aggregator"):
        return False
    if raw and raw.get("is_likely_article") is False:
        return False
    return is_likely_article_page(title or host, url)


async def download_html(url: str) -> str | None:
    settings = get_settings()
    timeout = httpx.Timeout(settings.gdelt_web_extract_timeout_s, connect=8.0)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CausaLensSEA/1.0; "
            "article-extractor; +https://github.com/venvennnn/causalens)"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        log.info(
            "gdelt_web_extract_failed",
            extra={"source": "gdelt", "url": url, "success": False, "error": type(exc).__name__},
        )
        return None
    if response.status_code >= 400:
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    if content_type and "html" not in content_type and "xml" not in content_type and "text/" not in content_type:
        return None
    return response.text[:400_000]
