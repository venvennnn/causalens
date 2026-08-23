from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dateutil import parser as date_parser

from app.models.schemas import Article, ArticleCandidate
from app.sources.registry import SOURCE_REGISTRY, get_source

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "spm",
    "ref",
    "ref_src",
}

CNA_PROMO_LINES = {
    "cna games",
    "guess word",
    "buzzword",
    "mini sudoku",
    "mini crossword",
    "word search",
    "show more",
    "show less",
}

UPLOADER_RE = re.compile(r"\n?\s*Uploaded by .+\s*$", re.IGNORECASE)


def article_id_for(url: str) -> str:
    canonical = canonicalize_url(url)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return (url or "").strip()
    host = parsed.hostname or ""
    host = host.lower()
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", urlencode(query), ""))


def parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = date_parser.parse(text, fuzzy=True)
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (ValueError, OverflowError, TypeError):
        return None


def _clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_cna_promos(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if line.strip().lower() in CNA_PROMO_LINES:
            continue
        lines.append(line)
    return _clean_text("\n".join(lines))


def strip_edge_uploader(body: str) -> str:
    return _clean_text(UPLOADER_RE.sub("", body))


def _first_str(record: dict, *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("url") or value.get("href") or value.get("value")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _categories(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,|/]", value) if part.strip()]
    return []


def _is_canonical_article_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    path = parsed.path or ""
    if "/fast/" in path:
        return False
    if path in ("", "/"):
        return False
    return True


def _pick_cna_url(record: dict) -> str:
    product = _first_str(record, "product_page_url") or ""
    article = _first_str(record, "article_url", "url") or ""
    nested = ""
    if isinstance(record.get("input"), dict):
        nested = str(record["input"].get("url") or "")
    if _is_canonical_article_url(product):
        return product
    if _is_canonical_article_url(article):
        return article
    if _is_canonical_article_url(nested) and "channelnewsasia.com/business" not in nested:
        return nested
    return product or article or nested


def normalize_discovery(source_key: str, record: dict) -> ArticleCandidate | None:
    source = get_source(source_key)
    if source_key == "cna":
        url = _pick_cna_url(record)
        title = _first_str(record, "title", "article_title") or ""
        published = parse_datetime(record.get("published_at") or record.get("publish_date"))
        categories = _categories(record.get("category") or record.get("categories"))
        summary = _first_str(record, "summary", "excerpt", "description")
        image_url = _first_str(record, "image_url", "featured_image", "image")
    elif source_key == "edge":
        url = _first_str(record, "article_url", "url", "product_page_url") or ""
        title = _first_str(record, "article_title", "title") or ""
        published = parse_datetime(record.get("publish_date") or record.get("published_at"))
        categories = _categories(record.get("categories") or record.get("category"))
        summary = _first_str(record, "summary", "excerpt")
        image_url = _first_str(record, "featured_image", "image_url", "image")
    else:
        url = _first_str(record, "article_url", "url", "link", "product_page_url") or ""
        if not url and isinstance(record.get("input"), dict):
            maybe = str(record["input"].get("url") or "")
            if maybe and maybe.rstrip("/") != source["discovery_url"].rstrip("/"):
                url = maybe
        title = _first_str(record, "article_title", "title", "headline") or ""
        published = parse_datetime(
            record.get("published_at")
            or record.get("publish_date")
            or record.get("date")
            or record.get("published")
        )
        categories = _categories(record.get("categories") or record.get("category") or record.get("tags"))
        summary = _first_str(record, "summary", "excerpt", "description", "lead")
        image_url = _first_str(record, "image_url", "featured_image", "image", "thumbnail")

    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    allowed = {domain.lower() for domain in source["domains"]}
    if host and host not in allowed and not any(host.endswith(domain) for domain in allowed):
        # Discovery pages can still emit off-domain links; keep same-source articles only.
        if source_key in SOURCE_REGISTRY:
            return None
    title = title or url
    canonical = canonicalize_url(url)
    return ArticleCandidate(
        id=article_id_for(canonical),
        title=title,
        url=canonical,
        source=source["name"],
        country=source["country"],
        published_at=published,
        category=categories,
        summary=summary,
        image_url=image_url,
        raw=record,
    )


def normalize_article(
    source_key: str,
    record: dict,
    *,
    url: str | None = None,
    candidate: ArticleCandidate | None = None,
) -> Article:
    source = get_source(source_key)
    resolved_url = url or _first_str(record, "url", "article_url", "product_page_url")
    if not resolved_url and isinstance(record.get("input"), dict):
        resolved_url = record["input"].get("url")
    if not resolved_url and candidate:
        resolved_url = candidate.url
    resolved_url = canonicalize_url(resolved_url or "")

    title = (
        _first_str(record, "article_title", "title", "headline")
        or (candidate.title if candidate else "")
        or resolved_url
    )
    body = _first_str(record, "article_text", "body", "content", "text", "article_body", "full_text") or ""
    if source_key == "cna":
        body = strip_cna_promos(body)
    elif source_key == "edge":
        body = strip_edge_uploader(body)
    else:
        body = _clean_text(body)

    author = _first_str(record, "author", "byline", "writer")
    if source_key == "cna":
        source_line = _first_str(record, "source")
        if source_line and source_line.lower().startswith("source:"):
            author = source_line.split(":", 1)[-1].strip() or author

    categories = _categories(record.get("category") or record.get("categories") or (candidate.category if candidate else []))
    published = parse_datetime(
        record.get("published_at")
        or record.get("publish_date")
        or record.get("date")
        or (candidate.published_at if candidate else None)
    )
    summary = _first_str(record, "summary", "excerpt", "description") or (candidate.summary if candidate else None)
    image_url = _first_str(record, "image_url", "featured_image", "image") or (candidate.image_url if candidate else None)

    return Article(
        id=article_id_for(resolved_url),
        title=title,
        url=resolved_url,
        source=source["name"],
        country=source["country"],
        language="en",
        published_at=published,
        author=author,
        category=categories,
        summary=summary,
        body=body,
        image_url=image_url,
        ingested_at=datetime.utcnow(),
        raw=record,
    )
