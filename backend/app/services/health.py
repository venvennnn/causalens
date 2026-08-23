from __future__ import annotations

import re

from app.models.schemas import Article, ValidationResult

NAV_HINTS = {
    "subscribe",
    "sign in",
    "log in",
    "cookie",
    "privacy policy",
    "terms of use",
    "advertisement",
    "newsletter",
    "follow us",
    "share this",
    "related stories",
    "most popular",
    "trending now",
}


def validate_article(article: Article) -> ValidationResult:
    failures: list[str] = []
    if not (article.title or "").strip():
        failures.append("missing_title")
    if not (article.url or "").strip():
        failures.append("missing_url")
    body = (article.body or "").strip()
    if len(body) < 250:
        failures.append("body_too_short")
    if body and _mostly_navigation(body):
        failures.append("body_mostly_navigation")
    return ValidationResult(healthy=not failures, failures=failures)


def _mostly_navigation(body: str) -> bool:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return True
    short_lines = sum(1 for line in lines if len(line) < 40)
    hint_hits = sum(1 for line in lines if line.lower() in NAV_HINTS or any(h in line.lower() for h in NAV_HINTS))
    words = re.findall(r"[A-Za-z]{2,}", body)
    if not words:
        return True
    return (short_lines / max(len(lines), 1) > 0.75 and hint_hits >= 4) or hint_hits / max(len(lines), 1) > 0.4
