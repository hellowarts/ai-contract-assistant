from __future__ import annotations

from typing import Any

from agents.checklist_agent import ChecklistAgent
from agents.contract_analyzer import ContractAnalyzer
from agents.document_agent import DocumentAgent
from agents.regulation_agent import RegulationAgent
from core.workflow_state import WorkflowState


class OutputFormatter:

    def format(self, target: WorkflowState | dict[str, Any]) -> str:

        return self.format_report(target)

    def format_report(self, target: WorkflowState | dict[str, Any]) -> str:

        state = self._coerce_state(target)
        contract = state.contract or {}
        regulation = state.regulation or {}
        documents = state.documents or {}
        checklist = state.checklist or {}
        evidence = state.evidence or []

        lines: list[str] = []
        lines.extend(self._section_header("계약 분석"))
        lines.extend(self._format_contract_section(contract))
        lines.append("")
        lines.extend(self._section_header("규정 판단"))
        lines.extend(self._format_regulation_section(regulation))
        lines.append("")
        lines.extend(self._section_header("근거(Evidence)"))
        lines.extend(self._format_evidence_section(evidence))
        lines.append("")
        lines.extend(self._section_header("제출서류"))
        lines.extend(self._format_documents_section(documents))
        lines.append("")
        lines.extend(self._section_header("체크리스트"))
        lines.extend(self._format_checklist_section(checklist))
        lines.append("")
        lines.extend(self._section_header("최종 검토"))
        lines.extend(self._format_final_review_section(state))

        return "\n".join(lines).strip()

    def format_detailed(self, target: WorkflowState | dict[str, Any]) -> str:

        return self.format_report(target)

    def print(self, target: WorkflowState | dict[str, Any]) -> None:

        print(self.format_report(target))

    def _coerce_state(self, target: WorkflowState | dict[str, Any]) -> WorkflowState:

        if isinstance(target, WorkflowState):

            return target

        state = WorkflowState()

        if isinstance(target, dict):

            state.contract = dict(target.get("contract", {}))
            state.regulation = dict(target.get("regulation", {}))
            state.documents = dict(target.get("documents", {}))
            state.checklist = dict(target.get("checklist", {}))
            state.outputs = dict(target.get("outputs", {}))
            state.evidence = list(target.get("evidence", []))
            state.logs = list(target.get("logs", []))

        return state

    def _section_header(self, title: str) -> list[str]:

        return [f"■ {title}"]

    def _format_contract_section(self, contract: dict[str, Any]) -> list[str]:

        lines: list[str] = []
        lines.append(f"- 계약유형: {self._stringify(contract.get('contract_type') or '미확인')}")
        lines.append(f"- 계약상대자: {self._stringify(contract.get('vendor') or '미확인')}")

        amount = contract.get("amount")
        amount_text = f"{amount:,}원" if isinstance(amount, int) else self._stringify(amount or '미확인')
        lines.append(f"- 계약금액: {amount_text}")

        start = contract.get("contract_start") or contract.get("period", {}).get("start") or "미확인"
        end = contract.get("contract_end") or contract.get("period", {}).get("end") or "미확인"
        lines.append(f"- 계약기간: {start} ~ {end}")
        lines.append(f"- 계약방식: {self._stringify(contract.get('contract_method') or '미확인')}")
        lines.append(f"- 계약명: {self._stringify(contract.get('title') or '미확인')}")

        return lines

    def _format_regulation_section(self, regulation: dict[str, Any]) -> list[str]:

        lines: list[str] = []
        lines.append(f"- 적용 규정명: {self._stringify(regulation.get('rule_name') or '미확인')}")
        lines.append(f"- 조문 번호: {self._stringify(regulation.get('article_no') or '미확인')}")
        lines.append(f"- 판단 결과: {self._stringify(regulation.get('decision') or '미확인')}")
        lines.append(f"- 판단 이유: {self._stringify(regulation.get('reason') or '미확인')}")
        lines.append(f"- 계약금액 연결 판단: {self._stringify(regulation.get('amount_reason') or '미확인')}")
        lines.append(f"- 계약방식 연결 판단: {self._stringify(regulation.get('method_reason') or '미확인')}")
        return lines

    def _format_evidence_section(self, evidence: list[Any]) -> list[str]:

        lines: list[str] = []

        if not evidence:

            return ["- (없음)"]

        for index, item in enumerate(evidence[:5], start=1):

            if isinstance(item, dict):

                kb_id = item.get("kb_id") or item.get("source") or "미확인"
                page = item.get("page")
                location = item.get("location") or "미확인"
                article_no = item.get("article_no")
                clause_no = item.get("clause_no")
                legal_ref = item.get("legal_ref")
                quote = item.get("quote") or item.get("decision") or item.get("title") or "미확인"
                body = item.get("body") or ""
                chunk = item.get("chunk") or item.get("snippet") or ""
                lines.append(f"- [{index}] KB ID: {kb_id}")
                if legal_ref or article_no or clause_no:
                    ref_text = legal_ref or " ".join(part for part in [article_no, clause_no] if part)
                    lines.append(f"  - 조문: {self._stringify(ref_text)}")
                lines.append(f"  - 위치: {location if page is None else f'{location} / p.{page}'}")
                lines.append(f"  - 인용 문장: {quote}")
                if body:
                    lines.append(f"  - 본문: {body}")
                if chunk:
                    lines.append(f"  - 검색된 Chunk: {chunk}")

            else:

                lines.append(f"- [{index}] {self._stringify(item)}")

        if len(evidence) > 5:

            lines.append(f"- ... and {len(evidence) - 5} more")

        return lines

    def _format_documents_section(self, documents: dict[str, Any]) -> list[str]:

        lines: list[str] = []
        records = documents.get("document_records") or []
        required_documents = documents.get("required_documents") or []

        if records:

            for index, item in enumerate(records, start=1):

                if isinstance(item, dict):

                    kb_id = item.get("kb_id") or "미확인"
                    location = item.get("location") or item.get("source") or "미확인"
                    quote = item.get("quote") or item.get("snippet") or "미확인"
                    lines.append(f"- [{index}] KB ID: {kb_id} / 위치: {location}")
                    lines.append(f"  - 제출서류: {quote}")
                    chunk = item.get("chunk")
                    if chunk:
                        lines.append(f"  - 근거 Chunk: {chunk}")

                else:

                    lines.append(f"- [{index}] {self._stringify(item)}")

            return lines

        if required_documents:

            for index, item in enumerate(required_documents, start=1):

                lines.append(f"- [{index}] {self._stringify(item)}")

            return lines

        return ["- (없음)"]

    def _format_checklist_section(self, checklist: dict[str, Any]) -> list[str]:

        lines: list[str] = []
        summary = checklist.get("summary") or {}
        basis = checklist.get("basis") or {}
        items = checklist.get("items") or []

        if isinstance(summary, dict):

            lines.append(
                f"- 요약: 총 {summary.get('total_items', 0)}항목 / 필수 {summary.get('required_items', 0)}항목 / 선택 {summary.get('optional_items', 0)}항목"
            )
        else:

            lines.append(f"- 요약: {self._stringify(summary)}")

        lines.append(f"- 기준: {self._stringify(basis)}")
        lines.append("- 항목:")

        if not items:

            lines.append("  - (없음)")
            return lines

        for index, item in enumerate(items, start=1):

            if isinstance(item, dict):

                status = item.get("status", "pending")
                required = item.get("required", False)
                title = item.get("title", "항목")
                detail = item.get("detail", "")
                lines.append(f"  - [{index}] ☐ {title} (필수={required}, 상태={status})")
                if detail:
                    lines.append(f"    - 확인 이유: {detail}")

            else:

                lines.append(f"  - [{index}] ☐ {self._stringify(item)}")

        return lines

    def _format_final_review_section(self, state: WorkflowState) -> list[str]:

        contract = state.contract or {}
        regulation = state.regulation or {}
        documents = state.documents or {}
        checklist = state.checklist or {}

        lines: list[str] = []
        contract_type = contract.get("contract_type") or "미확인"
        decision = regulation.get("decision") or "미확인"
        summary = documents.get("summary") or "미확인"
        checklist_summary = checklist.get("summary") or {}

        lines.append(f"- 계약유형 {contract_type} 기준으로 {self._stringify(decision)}")
        lines.append(f"- 제출서류 검토 결과: {self._stringify(summary)}")

        if isinstance(checklist_summary, dict):

            lines.append(
                f"- 체크리스트 상태: 총 {checklist_summary.get('total_items', 0)}항목 중 필수 {checklist_summary.get('required_items', 0)}항목 확인"
            )

        lines.append("- 최종 권고: 제출 전 계약기간, 계약방식, 최신본 여부 및 근거 문서를 최종 확인할 필요가 있음")

        return lines

    def _stringify(self, value: Any) -> str:

        if isinstance(value, str):

            return value

        return str(value)


def format_output(target: WorkflowState | dict[str, Any]) -> str:

    return OutputFormatter().format_report(target)


def main() -> None:

    analyzer = ContractAnalyzer()
    regulation_agent = RegulationAgent()
    document_agent = DocumentAgent()
    checklist_agent = ChecklistAgent()
    formatter = OutputFormatter()

    text = input("계약 내용을 입력하세요.\n> ")

    state = WorkflowState()
    state.contract = analyzer.analyze(text)
    regulation_agent.analyze(state)
    document_agent.analyze(state)
    checklist_agent.analyze(state)

    print()
    print(formatter.format_report(state))


if __name__ == "__main__":
    main()
