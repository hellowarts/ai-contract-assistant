from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agents.contract_analyzer import ContractAnalyzer
from core.kb_manager import KBManager
from core.pdf_loader import PDFLoader
from core.workflow_state import WorkflowState


class RegulationAgent:

    def __init__(self, kb_manager: KBManager | None = None, pdf_loader: PDFLoader | None = None):

        base_dir = Path(__file__).resolve().parents[1] / "kb"

        self.kb_manager = kb_manager or KBManager(base_dir)
        self.pdf_loader = pdf_loader or PDFLoader()

        self._kb_cache: dict[str, list[dict[str, Any]]] = {}

    def analyze(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        state = self._coerce_state(target)
        contract = state.contract or {}

        kb_id = "KB-001"
        kb_pages = self._load_kb_pages(kb_id)
        keywords = self._extract_keywords(contract)
        matched_excerpts = self._find_excerpts(kb_pages, keywords)

        rule_name = "지방자치단체 입찰 및 계약집행기준"
        article_no = self._extract_article_no(contract, matched_excerpts, kb_pages) or "관련 조항 확인 필요"
        reason = self._build_reason(contract, matched_excerpts)
        amount_reason = self._build_amount_reason(contract)
        method_reason = self._build_method_reason(contract)
        decision = self._build_decision(contract, rule_name, article_no)

        regulation = {
            "kb_ids": [kb_id],
            "rule_name": rule_name,
            "article_no": article_no,
            "contract_type": contract.get("contract_type"),
            "contract_method": contract.get("contract_method"),
            "contract_amount": contract.get("amount"),
            "decision": decision,
            "summary": self._build_summary(contract),
            "keywords": keywords,
            "reason": reason,
            "amount_reason": amount_reason,
            "method_reason": method_reason,
            "excerpts": matched_excerpts,
            "evidence": self._build_evidence(kb_id, matched_excerpts, contract, rule_name, article_no),
        }

        state.regulation = regulation
        state.evidence.extend(regulation["evidence"])
        state.logs.append({
            "agent": "RegulationAgent",
            "action": "analyze",
            "status": "ok",
            "kb_ids": [kb_id],
        })

        if isinstance(target, WorkflowState):

            return state

        return regulation

    def judge(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

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
            state.evidence = list(target.get("evidence", []))
            state.logs = list(target.get("logs", []))

        return state

    def _load_kb_pages(self, kb_id: str) -> list[dict[str, Any]]:

        if kb_id in self._kb_cache:

            return self._kb_cache[kb_id]

        path = self.kb_manager.get(kb_id)
        pages: list[dict[str, Any]] = []

        if path.exists():

            try:

                for document in self.pdf_loader.load(str(path)):

                    metadata = dict(getattr(document, "metadata", {}) or {})
                    metadata["kb_id"] = kb_id
                    metadata["source"] = path.name
                    metadata["page"] = metadata.get("page", metadata.get("page_number"))
                    content = self._clean_text(getattr(document, "page_content", ""))

                    if self._should_skip_page(content, metadata.get("page")):

                        continue

                    pages.append({
                        "kb_id": kb_id,
                        "source": path.name,
                        "page": metadata.get("page"),
                        "location": self._build_location(path.name, metadata.get("page")),
                        "content": content,
                        "metadata": metadata,
                    })

            except Exception:

                pages = []

        self._kb_cache[kb_id] = pages

        return pages

    def _should_skip_page(self, content: str, page_number: Any) -> bool:

        normalized = content.lower()

        if page_number == 1 and any(keyword in normalized for keyword in ("목차", "차례", "index")):

            return True

        return any(keyword in normalized for keyword in ("목차", "차례", "index"))

    def _extract_keywords(self, contract: dict[str, Any]) -> list[str]:

        keywords: list[str] = []

        risk_factors = contract.get("risk_factors")

        if isinstance(risk_factors, list):

            for item in risk_factors:

                if isinstance(item, str) and item.strip():

                    keywords.append(item.strip())

        for key in ("contract_type", "contract_method", "title", "business_name", "task_content", "vendor"):

            value = contract.get(key)

            if isinstance(value, str) and value.strip():

                keywords.append(value.strip())

        amount = contract.get("amount")

        if isinstance(amount, int):

            keywords.append(str(amount))
            keywords.append(f"{amount:,}원")

        if contract.get("estimated"):

            keywords.append("estimated")

        seen: set[str] = set()
        unique_keywords: list[str] = []

        for keyword in keywords:

            if keyword not in seen:

                seen.add(keyword)

                unique_keywords.append(keyword)

        return unique_keywords

    def _find_excerpts(self, kb_pages: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:

        excerpts: list[dict[str, Any]] = []
        seen: set[tuple[Any, Any, str]] = set()

        for page in kb_pages:

            content = page.get("content", "")

            if not content:

                continue

            for keyword in keywords:

                if keyword and keyword in content:

                    chunk = self._extract_chunk(content, keyword)
                    quote = self._extract_quote(content, keyword)
                    article_no, clause_no = self._extract_article_clause(chunk, content)
                    signature = (page.get("page"), page.get("location"), chunk)

                    if signature in seen:

                        continue

                    seen.add(signature)
                    excerpts.append({
                        "kb_id": page.get("kb_id"),
                        "page": page.get("page"),
                        "location": page.get("location"),
                        "legal_ref": self._build_legal_ref(article_no, clause_no),
                        "article_no": article_no,
                        "clause_no": clause_no,
                        "quote": quote,
                        "body": chunk,
                        "chunk": chunk,
                    })

                    break

            if len(excerpts) >= 8:

                break

        return excerpts

    def _extract_chunk(self, text: str, keyword: str, window: int = 180) -> str:

        cleaned = self._clean_text(text)
        index = cleaned.find(keyword)

        if index < 0:

            return self._truncate(cleaned, 260)

        start = max(0, index - window)
        end = min(len(cleaned), index + len(keyword) + window)

        return self._truncate(cleaned[start:end], 260)

    def _extract_quote(self, text: str, keyword: str) -> str:

        cleaned = self._clean_text(text)
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.。])\s+|\n+", cleaned) if sentence.strip()]

        for sentence in sentences:

            if keyword in sentence:

                return self._truncate(sentence, 220)

        return self._truncate(cleaned, 220)

    def _extract_article_no(self, contract: dict[str, Any], excerpts: list[dict[str, Any]], kb_pages: list[dict[str, Any]]) -> str | None:

        for item in excerpts:

            article = item.get("article_no")

            if isinstance(article, str) and article.strip():

                return article.strip()

        patterns = [
            re.compile(r"(제\d+조(?:의\d+)?(?:\([^\)]+\))?)"),
            re.compile(r"(\d+\.\s*[^0-9]{2,40})"),
            re.compile(r"(제\d+[장절])"),
        ]

        search_texts: list[str] = []
        preferred_terms = [
            contract.get("contract_method"),
            contract.get("contract_type"),
            contract.get("title"),
        ]

        preferred_terms = [term for term in preferred_terms if isinstance(term, str) and term.strip()]

        for item in excerpts:

            search_texts.append(str(item.get("quote") or ""))
            search_texts.append(str(item.get("chunk") or ""))

        for page in kb_pages:

            search_texts.append(page.get("content", ""))

        prioritized_texts = []
        if preferred_terms:

            for text in search_texts:

                if any(term in text for term in preferred_terms):

                    prioritized_texts.append(text)

        for text in prioritized_texts + search_texts:

            for pattern in patterns:

                match = pattern.search(text)

                if match:

                    return match.group(1).strip()

        return None

    def _extract_article_clause(self, primary_text: str, fallback_text: str) -> tuple[str | None, str | None]:

        article_pattern = re.compile(r"(제\d+조(?:의\d+)?)")
        clause_pattern = re.compile(r"(제\d+항)")

        article_match = article_pattern.search(primary_text) or article_pattern.search(fallback_text)
        clause_match = clause_pattern.search(primary_text) or clause_pattern.search(fallback_text)

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

    def _build_decision(self, contract: dict[str, Any], rule_name: str, article_no: str) -> str:

        contract_type = contract.get("contract_type") or "미확인"
        method = contract.get("contract_method") or "미확인"
        amount = contract.get("amount")
        amount_text = f"{amount:,}원" if isinstance(amount, int) else "금액 미확인"

        if method == "수의계약" and isinstance(amount, int) and amount > 20000000:

            verdict = "수의계약 추가 검토 필요"
        elif method == "수의계약":

            verdict = "수의계약 가능 여부 검토"
        else:

            verdict = f"{method} 방식 적용 여부 검토"

        return (
            f"{rule_name} {article_no}를 적용하여 {contract_type} 계약을 검토함. "
            f"계약금액 {amount_text}, 계약방식 {method}을 함께 고려하여 {verdict}으로 판단함."
        )

    def _build_reason(self, contract: dict[str, Any], excerpts: list[dict[str, Any]]) -> str:

        contract_type = contract.get("contract_type") or "미확인"
        method = contract.get("contract_method") or "미확인"
        amount = contract.get("amount")
        amount_text = f"{amount:,}원" if isinstance(amount, int) else "금액 미확인"
        first_quote = excerpts[0]["quote"] if excerpts else "관련 조문을 확인하지 못함"

        return (
            f"{contract_type} 계약으로 확인되며, 계약금액은 {amount_text}, 계약방식은 {method}이다. "
            f"KB-001의 확인 문구({first_quote})에 따라 관련 기준을 우선 검토한다."
        )

    def _build_amount_reason(self, contract: dict[str, Any]) -> str:

        amount = contract.get("amount")
        amount_text = f"{amount:,}원" if isinstance(amount, int) else "금액 미확인"
        method = contract.get("contract_method") or "미확인"

        return f"계약금액 {amount_text}이 확인되므로, {method} 방식과 결합하여 집행 기준 및 분할 여부를 함께 검토한다."

    def _build_method_reason(self, contract: dict[str, Any]) -> str:

        method = contract.get("contract_method") or "미확인"

        return f"계약방식 {method}은 관련 기준 적용 여부를 판단하는 핵심 요소이므로, KB-001과의 정합성을 확인한다."

    def _build_evidence(
        self,
        kb_id: str,
        excerpts: list[dict[str, Any]],
        contract: dict[str, Any],
        rule_name: str,
        article_no: str,
    ) -> list[dict[str, Any]]:

        evidence: list[dict[str, Any]] = []

        for item in excerpts[:5]:

            evidence.append({
                "kb_id": kb_id,
                "page": item.get("page"),
                "location": item.get("location"),
                "legal_ref": item.get("legal_ref") or self._build_legal_ref(item.get("article_no"), item.get("clause_no")),
                "article_no": item.get("article_no") or article_no,
                "clause_no": item.get("clause_no"),
                "quote": item.get("quote"),
                "body": item.get("body") or item.get("chunk"),
                "chunk": item.get("chunk"),
                "rule_name": rule_name,
            })

        if not evidence:

            evidence.append({
                "kb_id": kb_id,
                "page": None,
                "location": self._build_location("KB-001.pdf", None),
                "legal_ref": self._build_legal_ref(article_no, None),
                "quote": "관련 인용문을 찾지 못함",
                "body": "",
                "chunk": "",
                "rule_name": rule_name,
                "article_no": article_no,
                "clause_no": None,
            })

        if contract.get("contract_type") and len(evidence) < 5:

            evidence.append({
                "source": "contract",
                "type": "input",
                "contract_type": contract.get("contract_type"),
                "contract_method": contract.get("contract_method"),
                "amount": contract.get("amount"),
                "title": contract.get("title"),
            })

        return evidence[:5]

    def _build_summary(self, contract: dict[str, Any]) -> str:

        contract_type = contract.get("contract_type") or "미확인"
        title = contract.get("title") or "계약명 미확인"
        vendor = contract.get("vendor") or "업체명 미확인"

        amount = contract.get("amount")
        if isinstance(amount, int):

            amount_text = f"{amount:,}원"
        else:

            amount_text = "금액 미확인"

        method = contract.get("contract_method") or "계약방식 미확인"

        return f"{contract_type} / {title} / {vendor} / {amount_text} / {method}"

    def _build_location(self, source: str, page: Any) -> str:

        if page is None:

            return source

        return f"{source} p.{page}"

    def _clean_text(self, text: str) -> str:

        return re.sub(r"\s+", " ", str(text)).strip()

    def _truncate(self, text: str, limit: int) -> str:

        cleaned = self._clean_text(text)

        if len(cleaned) <= limit:

            return cleaned

        return cleaned[: limit - 1].rstrip() + "…"


def analyze_regulation(target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

    return RegulationAgent().analyze(target)


def judge_regulation(target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

    return RegulationAgent().judge(target)


def main() -> None:

    analyzer = ContractAnalyzer()
    agent = RegulationAgent()

    text = input("계약 내용을 입력하세요.\n> ")

    state = WorkflowState()
    state.contract = analyzer.analyze(text)

    agent.analyze(state)

    print()
    print("===== Regulation Agent =====")
    for key, value in state.regulation.items():

        print(f"{key:15}: {value}")


if __name__ == "__main__":

    main()
