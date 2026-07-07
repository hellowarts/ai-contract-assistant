from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.contract_analyzer import ContractAnalyzer
from agents.document_agent import DocumentAgent
from agents.regulation_agent import RegulationAgent
from core.workflow_state import WorkflowState


class ChecklistAgent:

    def analyze(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

        state = self._coerce_state(target)
        contract = state.contract or {}
        regulation = state.regulation or {}
        documents = state.documents or {}

        required_documents = self._normalize_items(documents.get("required_documents", []))
        retrieved_items = self._normalize_retrieved(documents.get("retrieved", []))

        items = self._build_items(contract, regulation, required_documents, retrieved_items)

        checklist = {
            "items": items,
            "summary": self._build_summary(items),
            "basis": self._build_basis(contract, regulation, documents),
            "evidence": self._build_evidence(contract, regulation, documents, items),
        }

        state.checklist = checklist
        state.evidence.extend(checklist["evidence"])
        state.logs.append({
            "agent": "ChecklistAgent",
            "action": "analyze",
            "status": "ok",
            "item_count": len(items),
        })

        if isinstance(target, WorkflowState):

            return state

        return checklist

    def create(self, target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

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
            state.checklist = dict(target.get("checklist", {}))
            state.evidence = list(target.get("evidence", []))
            state.logs = list(target.get("logs", []))

        return state

    def _build_items(
        self,
        contract: dict[str, Any],
        regulation: dict[str, Any],
        required_documents: list[str],
        retrieved_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        items: list[dict[str, Any]] = []

        contract_type = contract.get("contract_type") or "미확인"
        decision = regulation.get("decision") or "규정 판단 미확인"
        contract_method = contract.get("contract_method") or "미확인"
        contract_start = contract.get("contract_start") or contract.get("period", {}).get("start") or "미확인"
        contract_end = contract.get("contract_end") or contract.get("period", {}).get("end") or "미확인"
        amount = contract.get("amount")
        amount_text = f"{amount:,}원" if isinstance(amount, int) else "미확인"
        has_contract_type = bool(contract.get("contract_type"))
        has_amount = isinstance(amount, int)
        has_period = contract_start != "미확인" and contract_end != "미확인"
        has_method = bool(contract.get("contract_method"))
        has_decision = bool(regulation.get("decision"))

        items.append(self._item("계약유형", f"계약 유형: {contract_type}", True, "contract", "확인 완료" if has_contract_type else "추가 확인"))
        items.append(self._item("계약금액", f"계약금액: {amount_text}", True, "contract", "확인 완료" if has_amount else "추가 확인"))
        items.append(self._item("계약기간", f"계약기간: {contract_start} ~ {contract_end}", True, "contract", "확인 완료" if has_period else "추가 확인"))
        items.append(self._item("계약방식", f"계약방식: {contract_method}", True, "contract", "확인 완료" if has_method else "추가 확인"))
        items.append(self._item("규정 판단", f"규정 판단 결과: {decision}", True, "regulation", "확인 완료" if has_decision else "추가 확인"))

        items.append(self._item("계약서", "계약서 작성 여부와 서명·날인 여부를 확인한다.", False, "contract", "추가 확인"))
        items.append(self._item("견적서", "견적서 제출 여부와 금액 일치 여부를 확인한다.", False, "documents", "제출 필요"))
        items.append(self._item("사업자등록증", "사업자등록증 및 관련 증빙의 최신본 여부를 확인한다.", False, "documents", "제출 필요"))
        items.append(self._item("착수계", "착수계 제출 여부와 누락 여부를 확인한다.", False, "documents", "제출 필요"))
        items.append(self._item("계약기간 적정성", "계약기간과 사업 수행기간이 일치하는지 확인한다.", False, "contract", "추가 확인"))
        items.append(self._item("계약방식 적정성", f"계약방식 {contract_method}의 적정성을 검토한다.", False, "regulation", "추가 확인"))

        if required_documents:

            for document in required_documents:

                items.append(self._item(document, f"제출 여부와 최신본을 확인한다: {document}", False, "documents", "제출 필요"))

        elif retrieved_items:

            for item in retrieved_items[:5]:

                label = item.get("snippet") or item.get("source") or "확인 항목"
                items.append(self._item(label, f"문서 관련 근거를 확인한다: {label}", False, "documents", "추가 확인"))

        else:

            items.append(self._item("제출서류 재확인", "관련 제출서류 항목을 다시 확인한다.", False, "documents", "추가 확인"))

        if contract.get("amount"):

            amount_text = f"{contract.get('amount'):,}원" if isinstance(contract.get("amount"), int) else str(contract.get("amount"))
            items.append(self._item("금액 재확인", f"계약금액을 확인한다: {amount_text}.", False, "contract", "확인 완료"))

        return items

    def _build_summary(self, items: list[dict[str, Any]]) -> dict[str, Any]:

        total = len(items)
        required = sum(1 for item in items if item["required"])

        return {
            "total_items": total,
            "required_items": required,
            "optional_items": total - required,
        }

    def _build_basis(
        self,
        contract: dict[str, Any],
        regulation: dict[str, Any],
        documents: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "contract_type": contract.get("contract_type"),
            "regulation_decision": regulation.get("decision"),
            "document_kb_ids": documents.get("kb_ids", []),
        }

    def _build_evidence(
        self,
        contract: dict[str, Any],
        regulation: dict[str, Any],
        documents: dict[str, Any],
        items: list[dict[str, Any]],
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

        for kb_id in documents.get("kb_ids", []):

            evidence.append({
                "source": "documents",
                "type": "kb_id",
                "kb_id": kb_id,
            })

        evidence.append({
            "source": "checklist",
            "type": "items",
            "count": len(items),
        })

        return evidence

    def _normalize_items(self, items: list[Any]) -> list[str]:

        normalized: list[str] = []

        for item in items:

            if isinstance(item, str):

                value = item.strip()

            elif isinstance(item, dict):

                value = str(item.get("snippet") or item.get("content") or item.get("label") or item.get("name") or "").strip()

            else:

                value = str(item).strip()

            if value:

                normalized.append(value)

        unique: list[str] = []
        seen: set[str] = set()

        for value in normalized:

            if value not in seen:

                seen.add(value)

                unique.append(value)

        return unique

    def _normalize_retrieved(self, items: list[Any]) -> list[dict[str, Any]]:

        normalized: list[dict[str, Any]] = []

        for item in items:

            if isinstance(item, dict):

                normalized.append(item)

            else:

                normalized.append({"snippet": str(item)})

        return normalized

    def _item(self, title: str, detail: str, required: bool, source: str, status: str = "pending") -> dict[str, Any]:

        return {
            "title": title,
            "detail": detail,
            "required": required,
            "source": source,
            "status": status,
        }


def create_checklist(target: WorkflowState | dict[str, Any]) -> WorkflowState | dict[str, Any]:

    return ChecklistAgent().analyze(target)


def main() -> None:

    analyzer = ContractAnalyzer()
    regulation_agent = RegulationAgent()
    document_agent = DocumentAgent()
    checklist_agent = ChecklistAgent()

    text = input("계약 내용을 입력하세요.\n> ")

    state = WorkflowState()
    state.contract = analyzer.analyze(text)
    regulation_agent.analyze(state)
    document_agent.analyze(state)
    checklist_agent.analyze(state)

    print()
    print("===== Checklist Agent =====")
    for key, value in state.checklist.items():

        print(f"{key:15}: {value}")


if __name__ == "__main__":

    main()