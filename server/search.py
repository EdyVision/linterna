from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

_TOKEN = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)

_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "de",
    "el",
    "en",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "it",
    "la",
    "las",
    "los",
    "of",
    "on",
    "or",
    "que",
    "that",
    "the",
    "to",
    "un",
    "una",
    "was",
    "were",
    "with",
    "y",
}


def tokenize(text: str) -> list[str]:
    return [
        tok.lower()
        for tok in _TOKEN.findall(text or "")
        if len(tok) > 1 and tok.lower() not in _STOP
    ]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = float(sum(counts.values()) or 1)
    return {term: count / total for term, count in counts.items()}


def _idf(docs: Iterable[list[str]]) -> dict[str, float]:
    docs_list = list(docs)
    n = len(docs_list) or 1
    df: Counter[str] = Counter()
    for tokens in docs_list:
        df.update(set(tokens))
    return {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(term, 0.0) for term, weight in a.items())


def _norm(vec: dict[str, float]) -> float:
    return math.sqrt(sum(v * v for v in vec.values())) or 1.0


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    return _dot(a, b) / (_norm(a) * _norm(b))


def semantic_rank(
    query: str,
    memories: list[dict],
    *,
    limit: int = 25,
    min_score: float = 0.08,
) -> list[tuple[dict, float]]:
    """Cheap local topic ranking (TF-IDF cosine). No model download."""
    q_tokens = tokenize(query)
    if not q_tokens or not memories:
        return []

    docs = [tokenize(f"{m.get('title', '')} {m.get('transcript', '')}") for m in memories]
    idf = _idf(docs + [q_tokens])

    def weighted(tokens: list[str]) -> dict[str, float]:
        raw = _tf(tokens)
        return {term: tf * idf.get(term, 1.0) for term, tf in raw.items()}

    q_vec = weighted(q_tokens)
    scored: list[tuple[dict, float]] = []
    for memory, tokens in zip(memories, docs, strict=True):
        if not tokens:
            continue
        score = cosine(q_vec, weighted(tokens))
        if score >= min_score:
            scored.append((memory, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
