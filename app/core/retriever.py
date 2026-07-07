from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


class Retriever:

    def __init__(self, db):

        self.db = db

    def search(self, query: str, expansion_terms: list[str] | None = None, k: int = 5):

        candidate_queries = self._build_candidate_queries(query, expansion_terms)
        scored_hits: dict[tuple[Any, Any, Any, Any], dict[str, Any]] = {}

        for candidate_query in candidate_queries:

            try:

                hits = self.db.similarity_search(candidate_query, k=max(k * 2, 8))

            except Exception:

                continue

            for rank, hit in enumerate(hits, start=1):

                metadata = getattr(hit, "metadata", {}) or {}
                content = getattr(hit, "page_content", "") or ""
                signature = (
                    metadata.get("kb_id"),
                    metadata.get("source"),
                    metadata.get("page", metadata.get("page_number")),
                    metadata.get("row"),
                )

                score = self._score_hit(candidate_query, expansion_terms or [], content, rank)
                existing = scored_hits.get(signature)

                if existing is None or score > existing["score"]:

                    scored_hits[signature] = {
                        "hit": hit,
                        "score": score,
                        "candidate_query": candidate_query,
                    }

        ordered_hits = sorted(
            scored_hits.values(),
            key=lambda item: (-item["score"], str(getattr(item["hit"], "metadata", {}).get("kb_id", "")), str(getattr(item["hit"], "metadata", {}).get("source", ""))),
        )

        return [item["hit"] for item in ordered_hits[:k]]

    def _build_candidate_queries(self, query: str, expansion_terms: list[str] | None) -> list[str]:

        terms = [self._clean_term(term) for term in self._split_terms(query)]

        if expansion_terms:

            terms.extend(self._clean_term(term) for term in expansion_terms)

        unique_terms: list[str] = []
        seen: set[str] = set()

        for term in terms:

            if term and term not in seen:

                seen.add(term)

                unique_terms.append(term)

        candidate_queries: list[str] = []

        if query.strip():

            candidate_queries.append(query.strip())

        for size in range(min(6, len(unique_terms)), 0, -1):

            candidate_queries.append(" ".join(unique_terms[:size]))

        for term in unique_terms:

            candidate_queries.append(term)

        deduped: list[str] = []
        query_seen: set[str] = set()

        for candidate in candidate_queries:

            normalized = self._clean_term(candidate)

            if normalized and normalized not in query_seen:

                query_seen.add(normalized)

                deduped.append(normalized)

        return deduped

    def _score_hit(self, candidate_query: str, expansion_terms: list[str], content: str, rank: int) -> float:

        text = self._clean_term(content)
        query_terms = self._split_terms(candidate_query)

        score = max(1.0, 12.0 - rank)

        for term in query_terms:

            if term and term in text:

                score += 4.0

        for term in expansion_terms:

            normalized = self._clean_term(term)

            if normalized and normalized in text:

                score += 6.0

        if any(keyword in text for keyword in ("목차", "차례", "index", "INDEX")):

            score -= 8.0

        if "수의계약" in text:

            score += 3.0

        if any(keyword in text for keyword in ("계약집행기준", "계약방법", "지방계약", "계약서", "제출서류")):

            score += 2.5

        return score

    def _split_terms(self, text: str) -> list[str]:

        parts = re.split(r"\s+", str(text).strip())

        return [part for part in parts if part]

    def _clean_term(self, term: str) -> str:

        return re.sub(r"\s+", " ", str(term)).strip()