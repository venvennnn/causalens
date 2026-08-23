from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.gdelt.topics import TopicConfig, normalize_text


@dataclass
class PhraseHit:
    phrase: str
    group: str
    weight: float
    count: int
    ngram: str


@dataclass
class DocAccumulator:
    doc_id: int
    tech_terms: dict[str, float] = field(default_factory=dict)
    geo_terms: dict[str, float] = field(default_factory=dict)
    entity_terms: dict[str, float] = field(default_factory=dict)
    matched_quadgrams: list[str] = field(default_factory=list)
    total_match_frequency: int = 0

    def add(self, hit: PhraseHit) -> None:
        bucket = {
            "technology": self.tech_terms,
            "geography": self.geo_terms,
            "entity": self.entity_terms,
        }[hit.group]
        bucket[hit.phrase] = max(bucket.get(hit.phrase, 0.0), hit.weight)
        if hit.ngram not in self.matched_quadgrams:
            self.matched_quadgrams.append(hit.ngram)
            if len(self.matched_quadgrams) > 24:
                self.matched_quadgrams = self.matched_quadgrams[:24]
        self.total_match_frequency += max(hit.count, 1)

    def qualifies(self, required_groups: tuple[str, ...]) -> bool:
        groups = {
            "technology": self.tech_terms,
            "geography": self.geo_terms,
            "entity": self.entity_terms,
        }
        return all(groups.get(group) for group in required_groups)


class TermMatcher:
    def __init__(self, topic: TopicConfig) -> None:
        self.topic = topic
        self.phrases = topic.all_phrases()
        self._needles = [(f" {phrase} ", group, weight) for phrase, group, weight in self.phrases]

    def match_ngram(self, ngram: str, count: int = 1) -> list[PhraseHit]:
        padded = f" {normalize_text(ngram)} "
        if padded == "  ":
            return []
        hits: list[PhraseHit] = []
        for needle, group, weight in self._needles:
            if needle in padded:
                hits.append(
                    PhraseHit(
                        phrase=needle.strip(),
                        group=group,
                        weight=weight,
                        count=count,
                        ngram=ngram,
                    )
                )
        return hits


def aggregate_hits(rows: list[tuple[int, list[PhraseHit]]]) -> dict[int, DocAccumulator]:
    docs: dict[int, DocAccumulator] = defaultdict(lambda: DocAccumulator(doc_id=0))
    for doc_id, hits in rows:
        acc = docs[doc_id]
        acc.doc_id = doc_id
        for hit in hits:
            acc.add(hit)
    return dict(docs)


def parse_ngram_line(line: str) -> tuple[int, str, int] | None:
    raw = line.strip()
    if not raw:
        return None
    parts = raw.split("\t")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), parts[1], int(float(parts[2]))
    except (TypeError, ValueError):
        return None
