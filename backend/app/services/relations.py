from __future__ import annotations

from app.models.schemas import Article, CausalEdge, EdgeEvidence, Event

CAUSAL_RELATIONS = {
    "CAUSES",
    "CONTRIBUTES_TO",
    "TRIGGERS",
    "AFFECTS",
    "ENABLES",
    "CONSTRAINS",
    "RESPONDS_TO",
}

ALLOWED_RELATIONS = CAUSAL_RELATIONS | {"PART_OF", "RELATED_TO"}

RELATION_THRESHOLDS = {
    "CAUSES": 0.80,
    "TRIGGERS": 0.80,
    "CONTRIBUTES_TO": 0.68,
    "ENABLES": 0.68,
    "CONSTRAINS": 0.68,
    "RESPONDS_TO": 0.68,
    "AFFECTS": 0.62,
    "PART_OF": 0.55,
    "RELATED_TO": 0.45,
}

DOWNGRADE_PATH = {
    "CAUSES": "CONTRIBUTES_TO",
    "TRIGGERS": "CONTRIBUTES_TO",
    "CONTRIBUTES_TO": "RELATED_TO",
    "ENABLES": "RELATED_TO",
    "CONSTRAINS": "RELATED_TO",
    "AFFECTS": "RELATED_TO",
    "RESPONDS_TO": "RELATED_TO",
    "PART_OF": "RELATED_TO",
}

CAUSAL_CUES = (
    "because",
    "due to",
    "as a result",
    "resulting in",
    "led to",
    "leading to",
    "driven by",
    "has driven",
    "have driven",
    "caused",
    "causing",
    "prompted",
    "forced",
    "triggered",
    "in response to",
    "following constraints",
    "on the back of",
    "spurred",
    "fuelled",
    "fueled",
)


def normalize_relation_label(value: str | None) -> str:
    label = (value or "RELATED_TO").strip().upper().replace(" ", "_")
    aliases = {
        "CAUSE": "CAUSES",
        "CAUSED": "CAUSES",
        "DRIVES": "CAUSES",
        "DROVE": "CAUSES",
        "DRIVE": "CAUSES",
        "CONTRIBUTE": "CONTRIBUTES_TO",
        "CONTRIBUTED_TO": "CONTRIBUTES_TO",
        "AFFECT": "AFFECTS",
        "AFFECTED": "AFFECTS",
        "ENABLE": "ENABLES",
        "CONSTRAINT": "CONSTRAINS",
        "RELATED": "RELATED_TO",
        "SIMILAR": "RELATED_TO",
        "ASSOCIATED": "RELATED_TO",
        "POSSIBLY_CONTRIBUTES_TO": "RELATED_TO",
    }
    label = aliases.get(label, label)
    if label not in ALLOWED_RELATIONS:
        return "RELATED_TO"
    return label


def events_share_article(source: Event, target: Event) -> set[str]:
    return set(source.source_article_ids or []) & set(target.source_article_ids or [])


def supporting_is_same_article(edge: CausalEdge, source: Event, target: Event) -> bool:
    shared = events_share_article(source, target)
    if shared:
        return True
    supporting = set(edge.supporting_article_ids or [])
    if not supporting:
        return False
    return bool(supporting & set(source.source_article_ids or [])) and bool(
        supporting & set(target.source_article_ids or [])
    ) and bool(supporting & set(source.source_article_ids or []) & set(target.source_article_ids or []))


def evidence_has_causal_language(edge: CausalEdge, articles: dict[str, Article]) -> bool:
    blobs: list[str] = [edge.reason or ""]
    for article_id in edge.supporting_article_ids:
        article = articles.get(article_id)
        if article is None:
            continue
        blobs.append(article.title or "")
        blobs.append((article.body or "")[:2500])
        blobs.append(article.summary or "")
    text = " ".join(blobs).lower()
    return any(cue in text for cue in CAUSAL_CUES)


def snippet_for_article(article: Article | None, limit: int = 280) -> str:
    if article is None:
        return ""
    body = (article.body or article.summary or "").replace("\n", " ").strip()
    if not body:
        return article.title
    return body[:limit].rstrip() + ("…" if len(body) > limit else "")


def downgrade_relation(relation: str) -> str:
    return DOWNGRADE_PATH.get(relation, "RELATED_TO")


def apply_relation_policy(
    edge: CausalEdge,
    source: Event,
    target: Event,
    articles: dict[str, Article],
) -> CausalEdge:
    relation = normalize_relation_label(edge.relation)
    same_article = supporting_is_same_article(edge, source, target)
    score = max(edge.evidence_score, edge.confidence)
    causal_language = evidence_has_causal_language(edge, articles)

    if relation in CAUSAL_RELATIONS and not same_article:
        relation = "RELATED_TO"
        if not (edge.reason or "").lower().startswith("cross-article"):
            edge.reason = (
                "Cross-article association without a source that asserts the link; stored as RELATED_TO. "
                + (edge.reason or "")
            ).strip()

    if relation in CAUSAL_RELATIONS and same_article and not causal_language:
        relation = "CONTRIBUTES_TO" if relation == "CAUSES" else "RELATED_TO"
        if relation == "RELATED_TO":
            edge.reason = (
                "No explicit causal language in the supporting article; defaulting to RELATED_TO. "
                + (edge.reason or "")
            ).strip()

    threshold = RELATION_THRESHOLDS.get(relation, 0.45)
    while score < threshold and relation != "RELATED_TO":
        relation = downgrade_relation(relation)
        threshold = RELATION_THRESHOLDS.get(relation, 0.45)

    if relation == "RELATED_TO" and score < RELATION_THRESHOLDS["RELATED_TO"]:
        edge.status = "inferred"

    edge.relation = relation  # type: ignore[assignment]
    if not edge.explanation:
        edge.explanation = edge.reason
    if not edge.evidence:
        edge.evidence = [
            EdgeEvidence(
                article_id=article_id,
                quote_or_snippet=snippet_for_article(articles.get(article_id)),
                reason=edge.reason,
            )
            for article_id in edge.supporting_article_ids[:3]
        ]
    return edge
