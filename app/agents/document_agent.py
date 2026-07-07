from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from agents.contract_analyzer import ContractAnalyzer
from agents.regulation_agent import RegulationAgent
from core.kb_manager import KBManager
from core.pdf_loader import PDFLoader
from core.retriever import Retriever
from core.vector_store import VectorStore
from core.workflow_state import WorkflowState

from langchain_core.documents import Document


class DocumentAgent:

    def __init__(
        self,
        kb_manager: KBManager | None = None,
        pdf_loader: PDFLoader | None = None,
        vector_store: VectorStore | None = None,
    ):

        base_dir = Path(__file__).resolve().parents[1] / "kb"

        self.kb_manager = kb_manager or KBManager(base_dir)
        self.pdf_loader = pdf_loader or PDFLoader()
        self.vector_store = vector_store or VectorStore()

        self.kb_ids = ["KB-002", "KB-003", "KB-004", "KB-005"]
        self._documents: list[Document] = []
        self._retriever: Retriever | None = None
        self._index_ready = False

    def analyze(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        state = self._coerce_state(target)
        contract = state.contract or {}
        regulation = state.regulation or {}

        query = self._build_query(contract, regulation)
        expansion_terms = self._build_query_expansion(contract, regulation)
        retrieved = self._search(query, expansion_terms)
        required_documents = self._extract_required_documents(retrieved)
        document_records = self._build_document_records(retrieved)

        documents = {
            "kb_ids": list(self.kb_ids),
            "query": query,
            "query_expansion": expansion_terms,
            "required_documents": required_documents,
            "document_records": document_records,
            "retrieved": retrieved,
            "summary": self._build_summary(contract, regulation, required_documents),
            "evidence": self._build_evidence(document_records, contract, regulation),
            "search_status": self._build_search_status(retrieved, document_records),
        }

        state.documents = documents
        state.evidence.extend(documents["evidence"])
        state.logs.append({
            "agent": "DocumentAgent",
            "action": "analyze",
            "status": "ok",
            "kb_ids": list(self.kb_ids),
        })

        if isinstance(target, WorkflowState):

            return state

        return documents

    def review(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        return self.analyze(target)

    def run(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        return self.analyze(target)

    def update_state(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        return self.analyze(target)

    def _coerce_state(self, target: WorkflowState | dict[str, Any]) -> WorkflowState:

        if isinstance(target, WorkflowState):

            return target

        state = WorkflowState()

        if isinstance(target, dict):

            state.contract = dict(target.get("contract", target))
            state.regulation = dict(target.get("regulation", {}))
            state.documents = dict(target.get("documents", {}))
            state.evidence = list(target.get("evidence", []))
            state.logs = list(target.get("logs", []))

        return state

    def _build_query(self, contract: dict[str, Any], regulation: dict[str, Any]) -> str:

        parts = [
            contract.get("contract_type"),
            contract.get("title"),
            contract.get("vendor"),
            regulation.get("decision"),
            regulation.get("summary"),
        ]

        query = " ".join(str(part).strip() for part in parts if part)

        return query.strip() or "용역 제출서류 확인"

    def _search(self, query: str, expansion_terms: list[str]) -> list[dict[str, Any]]:

        self._ensure_index()

        results: list[dict[str, Any]] = []

        if self._retriever is not None:

            try:

                hits = self._retriever.search(query, expansion_terms=expansion_terms, k=8)

                for hit in hits[:5]:

                    results.append(self._format_hit(hit))

            except Exception:

                results = []

        if results:

            return results

        return self._fallback_search(query, expansion_terms)

    def _ensure_index(self) -> None:

        if self._index_ready:

            return

        documents = self._load_documents()

        if not documents:

            self._index_ready = True
            return

        if not os.getenv("OPENAI_API_KEY"):

            self._retriever = None
            self._documents = documents
            self._index_ready = True
            return

        try:

            db = self.vector_store.build(documents)
            self._retriever = Retriever(db)
            self._documents = documents

        except Exception:

            self._retriever = None
            self._documents = documents

        self._index_ready = True

    def _load_documents(self) -> list[Document]:

        documents: list[Document] = []

        for kb_id in self.kb_ids:

            path = self.kb_manager.get(kb_id)

            documents.extend(self._load_kb_documents(kb_id, path))

        return self._chunk_documents(documents)

    def _load_kb_documents(self, kb_id: str, path: Path) -> list[Document]:

        if not path.exists():

            return []

        suffix = path.suffix.lower()

        if suffix == ".pdf":

            loaded: list[Document] = []

            try:

                for page in self.pdf_loader.load(str(path)):

                    content = getattr(page, "page_content", "")
                    metadata = dict(getattr(page, "metadata", {}) or {})
                    page_number = metadata.get("page", metadata.get("page_number"))

                    if content and not self._should_skip_page(content, page_number):

                        loaded.append(Document(page_content=content, metadata={"kb_id": kb_id, "source": path.name, "page": page_number}))

            except Exception:

                return []

            return loaded

        if suffix in {".xlsx", ".xls"}:

            try:

                frame = pd.read_excel(path)

            except Exception:

                return []

            rows: list[Document] = []

            for index, row in frame.fillna("").iterrows():

                text = " | ".join(str(value).strip() for value in row.tolist() if str(value).strip())

                if text:

                    rows.append(Document(page_content=text, metadata={"kb_id": kb_id, "source": path.name, "row": int(index)}))

            return rows

        return []

    def _should_skip_page(self, content: str, page_number: Any) -> bool:

        normalized = self._clean_text(content)
        toc_keywords = ("목차", "차례", "INDEX", "index")

        if page_number == 1 and any(keyword.lower() in normalized.lower() for keyword in toc_keywords):

            return True

        return any(keyword.lower() in normalized.lower() for keyword in toc_keywords)

    def _chunk_documents(self, documents: list[Document], chunk_size: int = 800, overlap: int = 120) -> list[Document]:

        chunks: list[Document] = []

        for document in documents:

            text = self._clean_text(document.page_content)

            if not text:

                continue

            start = 0

            while start < len(text):

                end = min(len(text), start + chunk_size)
                chunk_text = text[start:end].strip()

                if chunk_text:

                    article_no, clause_no = self._extract_article_clause(chunk_text)
                    chunk_metadata = dict(document.metadata)
                    chunk_metadata["article_no"] = article_no
                    chunk_metadata["clause_no"] = clause_no
                    chunk_metadata["legal_ref"] = self._build_legal_ref(article_no, clause_no)
                    chunk_metadata["body"] = self._shorten(chunk_text, 320)

                    chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))

                if end >= len(text):

                    break

                start = max(end - overlap, start + 1)

        return chunks

    def _extract_article_clause(self, text: str) -> tuple[str | None, str | None]:

        article_pattern = re.compile(r"(제\d+조(?:의\d+)?)")
        clause_pattern = re.compile(r"(제\d+항)")

        article_match = article_pattern.search(text)
        clause_match = clause_pattern.search(text)

        article_no = article_match.group(1).strip() if article_match else None
        clause_no = clause_match.group(1).strip() if clause_match else None

        return article_no, clause_no

    def _build_legal_ref(self, article_no: str | None, clause_no: str | None) -> str:

        if article_no and clause_no:

            return f"{article_no} {clause_no}"

        if article_no:

            return article_no

        if clause_no:

            return clause_no

        return "관련 조문 확인 필요"

    def _fallback_search(self, query: str, expansion_terms: list[str]) -> list[dict[str, Any]]:

        if not self._documents:

            return []

        keywords = self._build_keywords(query, expansion_terms)
        results: list[dict[str, Any]] = []

        for document in self._documents:

            text = document.page_content

            if not text:

                continue

            score = sum(1 for keyword in keywords if keyword in text)

            if score:

                results.append({
                    "kb_id": document.metadata.get("kb_id"),
                    "source": document.metadata.get("source"),
                    "page": document.metadata.get("page"),
                    "row": document.metadata.get("row"),
                    "location": self._build_location(document.metadata.get("source"), document.metadata.get("page"), document.metadata.get("row")),
                    "score": score,
                    "snippet": self._shorten(text),
                })

        results.sort(key=lambda item: (-item["score"], str(item.get("kb_id", "")), str(item.get("source", ""))))

        return results[:5]

    def _format_hit(self, hit: Any) -> dict[str, Any]:

        metadata = getattr(hit, "metadata", {}) or {}
        content = getattr(hit, "page_content", "") or str(hit)
        page = metadata.get("page", metadata.get("page_number"))
        row = metadata.get("row")

        return {
            "kb_id": metadata.get("kb_id"),
            "source": metadata.get("source"),
            "page": page,
            "row": row,
            "location": self._build_location(metadata.get("source"), page, row),
            "legal_ref": metadata.get("legal_ref"),
            "article_no": metadata.get("article_no"),
            "clause_no": metadata.get("clause_no"),
            "body": metadata.get("body"),
            "snippet": self._shorten(content),
        }

    def _build_query_expansion(self, contract: dict[str, Any], regulation: dict[str, Any]) -> list[str]:

        expansion_terms: list[str] = []

        contract_type = contract.get("contract_type")
        contract_method = contract.get("contract_method")
        contract_title = contract.get("title")
        amount = contract.get("amount")
        decision = regulation.get("decision")

        if isinstance(contract_type, str):

            if contract_type == "용역":

                expansion_terms.extend(["용역계약", "용역 제출서류", "착수계", "계약방법", "계약집행기준"])
            elif contract_type == "물품":

                expansion_terms.extend(["물품계약", "물품 제출서류", "검수", "계약방법"])
            elif contract_type == "공사":

                expansion_terms.extend(["공사계약", "공사 제출서류", "계약방법", "현장설명"])

        if isinstance(contract_method, str):

            if contract_method == "수의계약":

                expansion_terms.extend(["지방계약", "계약방법", "수의계약 가능", "수의계약 요건", "계약집행기준"])
            elif contract_method in {"일반경쟁", "제한경쟁", "지명경쟁"}:

                expansion_terms.extend([contract_method, "계약방법", "경쟁입찰", "입찰방법"])

        if isinstance(contract_title, str) and contract_title.strip():

            expansion_terms.extend([contract_title.strip(), "계약서", "제출서류"])

        if isinstance(amount, int):

            expansion_terms.extend(self._amount_expansions(amount))

        if isinstance(decision, str) and decision.strip():

            expansion_terms.extend([decision.strip(), "판단", "근거"])

        expansion_terms.extend(["지방자치단체", "입찰", "계약집행기준", "제출서류", "착수계", "견적서"])

        unique_terms: list[str] = []
        seen: set[str] = set()

        for term in expansion_terms:

            normalized = self._clean_text(term)

            if normalized and normalized not in seen:

                seen.add(normalized)

                unique_terms.append(normalized)

        return unique_terms

    def _amount_expansions(self, amount: int) -> list[str]:

        expansions = [f"{amount:,}원"]

        if amount % 10000 == 0:

            expansions.append(f"{amount // 10000:,}만원")

        if amount >= 1000000:

            expansions.append(f"{amount / 1000000:g}백만원")

        if amount >= 10000:

            expansions.append(f"{amount // 10000}만원")

        if amount == 25000000:

            expansions.extend(["2500만원", "2,500만원", "2천5백만원", "25,000,000원"])

        return expansions

    def _build_keywords(self, query: str, expansion_terms: list[str]) -> list[str]:

        keywords = [term for term in self._split_keywords(query) if term]
        keywords.extend(expansion_terms)

        unique: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:

            normalized = self._clean_text(keyword)

            if normalized and normalized not in seen:

                seen.add(normalized)

                unique.append(normalized)

        return unique

    def _extract_required_documents(self, retrieved: list[dict[str, Any]]) -> list[str]:

        candidates: list[str] = []
        candidate_seen: set[str] = set()

        for item in retrieved:

            snippet = item.get("snippet", "")

            for phrase in self._split_sentences(snippet) + self._split_document_fragments(snippet):

                if any(token in phrase for token in ["제출", "서류", "원본", "사본", "계약", "확인"]):

                    short_phrase = self._shorten_phrase(phrase)

                    if short_phrase and short_phrase not in candidate_seen:

                        candidate_seen.add(short_phrase)

                        candidates.append(short_phrase)

        unique: list[str] = []
        unique_seen: set[str] = set()

        for phrase in candidates:

            normalized = phrase.strip()

            if normalized and normalized not in unique_seen:

                unique_seen.add(normalized)

                unique.append(normalized)

            if len(unique) >= 8:

                break

        if not unique:

            for item in retrieved[:5]:

                snippet = self._shorten_phrase(item.get("snippet", ""), limit=120)

                if snippet and snippet not in unique_seen:

                    unique_seen.add(snippet)

                    unique.append(snippet)

                if len(unique) >= 5:

                    break

        return unique

    def _build_search_status(self, retrieved: list[dict[str, Any]], document_records: list[dict[str, Any]]) -> dict[str, Any]:

        return {
            "retrieved_count": len(retrieved),
            "document_record_count": len(document_records),
            "success": bool(document_records),
        }

    def _build_document_records(self, retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:

        records: list[dict[str, Any]] = []
        seen: set[tuple[Any, Any, str]] = set()

        for item in retrieved:

            snippet = item.get("snippet", "")
            location = item.get("location") or self._build_location(item.get("source"), item.get("page"), item.get("row"))

            for fragment in self._split_sentences(snippet) + self._split_document_fragments(snippet):

                cleaned_fragment = self._shorten_phrase(fragment, limit=220)

                if not cleaned_fragment:

                    continue

                if not any(token in cleaned_fragment for token in ["제출", "서류", "원본", "사본", "계약", "확인", "기재", "첨부", "제출서류"]):

                    continue

                signature = (item.get("kb_id"), location, cleaned_fragment)

                if signature in seen:

                    continue

                seen.add(signature)

                records.append({
                    "kb_id": item.get("kb_id"),
                    "source": item.get("source"),
                    "page": item.get("page"),
                    "row": item.get("row"),
                    "location": location,
                    "quote": cleaned_fragment,
                    "chunk": self._truncate(snippet, 260),
                })

        return records

    def _shorten_phrase(self, text: str, limit: int = 140) -> str:

        cleaned = self._clean_text(text)

        if len(cleaned) <= limit:

            return cleaned

        return cleaned[: limit - 1].rstrip() + "…"

    def _truncate(self, text: str, limit: int = 220) -> str:

        cleaned = self._clean_text(text)

        if len(cleaned) <= limit:

            return cleaned

        return cleaned[: limit - 1].rstrip() + "…"

    def _build_summary(
        self,
        contract: dict[str, Any],
        regulation: dict[str, Any],
        required_documents: list[str],
    ) -> str:

        contract_type = contract.get("contract_type") or "미확인"
        decision = regulation.get("decision") or "규정 판단 미확인"
        count = len(required_documents)

        return f"{contract_type} 제출서류 검토: {decision} / 확인 항목 {count}건"

    def _build_evidence(
        self,
        document_records: list[dict[str, Any]],
        contract: dict[str, Any],
        regulation: dict[str, Any],
    ) -> list[dict[str, Any]]:

        evidence: list[dict[str, Any]] = []

        if contract.get("title"):

            evidence.append({
                "source": "contract",
                "type": "input",
                "title": contract.get("title"),
                "contract_type": contract.get("contract_type"),
            })

        if regulation.get("decision"):

            evidence.append({
                "source": "regulation",
                "type": "decision",
                "decision": regulation.get("decision"),
            })

        for item in document_records:

            evidence.append({
                "source": item.get("source"),
                "type": "kb_excerpt",
                "kb_id": item.get("kb_id"),
                "page": item.get("page"),
                "row": item.get("row"),
                "location": item.get("location"),
                "quote": item.get("quote"),
                "chunk": item.get("chunk"),
            })

        return evidence

    def _shorten(self, text: str, limit: int = 220) -> str:

        cleaned = self._clean_text(text)

        if len(cleaned) <= limit:

            return cleaned

        return cleaned[: limit - 1].rstrip() + "…"

    def _clean_text(self, text: str) -> str:

        text = re.sub(r"\s+", " ", str(text))

        return text.strip()

    def _split_sentences(self, text: str) -> list[str]:

        text = self._clean_text(text)

        if not text:

            return []

        pieces = re.split(r"(?<=[\.\?\!。])\s+|\n+", text)

        return [piece.strip() for piece in pieces if piece.strip()]

    def _split_document_fragments(self, text: str) -> list[str]:

        cleaned = self._clean_text(text)

        if not cleaned:

            return []

        fragments = re.split(r"(?=\d+\s*[\.|\)])|(?=연번)|(?=참고서식)|(?=제출서류)|(?=계약 시)|(?=착수 시)", cleaned)

        return [fragment.strip() for fragment in fragments if fragment.strip()]

    def _build_location(self, source: str | None, page: Any = None, row: Any = None) -> str:

        location_parts = [part for part in [source, f"p.{page}" if page is not None else None, f"row {row}" if row is not None else None] if part]

        return " / ".join(location_parts) if location_parts else "unknown"

    def _split_keywords(self, text: str) -> list[str]:

        text = self._clean_text(text)

        if not text:

            return []

        parts = [part.strip() for part in re.split(r"[\/|,]", text) if part.strip()]

        tokens = parts[:]

        for part in parts:

            tokens.extend(token for token in part.split() if token)

        unique: list[str] = []
        seen: set[str] = set()

        for token in tokens:

            if token not in seen:

                seen.add(token)

                unique.append(token)

        return unique


def analyze_documents(target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

    return DocumentAgent().analyze(target)


def review_documents(target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

    return DocumentAgent().review(target)


def main() -> None:

    analyzer = ContractAnalyzer()
    regulation_agent = RegulationAgent()
    document_agent = DocumentAgent()

    text = input("계약 내용을 입력하세요.\n> ")

    state = WorkflowState()
    state.contract = analyzer.analyze(text)
    regulation_agent.analyze(state)
    document_agent.analyze(state)

    print()
    print("===== Document Agent =====")
    for key, value in state.documents.items():

        print(f"{key:18}: {value}")


if __name__ == "__main__":

    main()