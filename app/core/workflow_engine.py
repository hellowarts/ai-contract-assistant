from __future__ import annotations

from typing import Any

from agents.checklist_agent import ChecklistAgent
from agents.contract_analyzer import ContractAnalyzer
from agents.document_agent import DocumentAgent
from agents.output_formatter import OutputFormatter
from agents.regulation_agent import RegulationAgent
from agents.supervisor import Supervisor
from core.llm_client import verify_ai_ready
from core.prompt_loader import PromptLoader
from core.workflow_state import WorkflowState


class WorkflowEngine:

    def __init__(
        self,
        supervisor: Supervisor | None = None,
        contract_analyzer: ContractAnalyzer | None = None,
        regulation_agent: RegulationAgent | None = None,
        document_agent: DocumentAgent | None = None,
        checklist_agent: ChecklistAgent | None = None,
        output_formatter: OutputFormatter | None = None,
    ) -> None:

        self.supervisor = supervisor or Supervisor()
        self.contract_analyzer = contract_analyzer or ContractAnalyzer()
        self.regulation_agent = regulation_agent or RegulationAgent()
        self.document_agent = document_agent or DocumentAgent()
        self.checklist_agent = checklist_agent or ChecklistAgent()
        self.output_formatter = output_formatter or OutputFormatter()
        self.llm = verify_ai_ready()
        self.prompt_loader = PromptLoader()

    def run(self, text: str, state: WorkflowState | None = None) -> WorkflowState:

        workflow_state = state or WorkflowState()
        workflow_state.request = {
            "text": text,
        }

        workflow_state.contract = self.contract_analyzer.analyze(text)
        self.supervisor.update_progress(workflow_state)

        self.regulation_agent.analyze(workflow_state)
        self.supervisor.update_progress(workflow_state)

        self.document_agent.analyze(workflow_state)
        self.supervisor.update_progress(workflow_state)

        self.checklist_agent.analyze(workflow_state)
        self.supervisor.update_progress(workflow_state)

        final_output = self._generate_final_output(workflow_state)
        workflow_state.outputs = {
            "final_output": final_output,
            "mode": "ai",
        }
        self.supervisor.update_progress(workflow_state)

        workflow_state.logs.append({
            "agent": "WorkflowEngine",
            "action": "run",
            "status": "ok",
            "completed_steps": workflow_state.progress.get("completed_steps", []),
        })

        return workflow_state

    def _generate_final_output(self, workflow_state: WorkflowState) -> str:

        prompt = self._build_final_prompt(workflow_state)

        try:

            response = self.llm.invoke(prompt)

        except Exception as exc:

            raise RuntimeError("AI 최종 응답 생성에 실패했습니다. 실행을 중단합니다.") from exc

        content = getattr(response, "content", "")

        if not str(content).strip():

            raise RuntimeError("AI 최종 응답이 비어 있습니다. 실행을 중단합니다.")

        return str(content).strip()

    def _build_final_prompt(self, workflow_state: WorkflowState) -> str:

        prompt_template = self.prompt_loader.load("final_response_prompt.md")
        input_data = self._build_input_data(workflow_state)

        return prompt_template.replace("{input_data}", input_data)

    def _build_input_data(self, workflow_state: WorkflowState) -> str:

        contract = workflow_state.contract or {}
        regulation = workflow_state.regulation or {}
        documents = workflow_state.documents or {}
        checklist = workflow_state.checklist or {}
        evidence = workflow_state.evidence or []

        lines: list[str] = []
        lines.append("[계약 분석 데이터]")
        for key in (
            "contract_type",
            "vendor",
            "amount",
            "title",
            "contract_start",
            "contract_end",
            "contract_method",
            "estimated",
        ):
            lines.append(f"- {key}: {contract.get(key)}")

        period = contract.get("period", {})
        if isinstance(period, dict):
            lines.append(f"- period.start: {period.get('start')}")
            lines.append(f"- period.end: {period.get('end')}")

        lines.append("")
        lines.append("[규정 판단 데이터]")
        for key in (
            "kb_ids",
            "contract_type",
            "decision",
            "summary",
            "rule_name",
            "article_no",
            "reason",
            "amount_reason",
            "method_reason",
        ):
            lines.append(f"- {key}: {regulation.get(key)}")

        lines.append("")
        lines.append("[근거 데이터]")
        for index, item in enumerate(evidence[:5], start=1):
            lines.append(f"- evidence[{index}]: {item}")
        lines.append(f"- evidence_count_total: {len(evidence)}")

        lines.append("")
        lines.append("[제출서류 데이터]")
        for key in ("kb_ids", "query", "summary"):
            lines.append(f"- {key}: {documents.get(key)}")
        lines.append(f"- document_records_count: {len(documents.get('document_records', []))}")
        lines.append("- required_documents:")
        for item in documents.get("required_documents", []):
            lines.append(f"  - {item}")
        lines.append("- document_records:")
        for item in documents.get("document_records", []):
            lines.append(f"  - {item}")
        lines.append("- retrieved:")
        for item in documents.get("retrieved", []):
            lines.append(f"  - {item}")

        lines.append("")
        lines.append("[체크리스트 데이터]")
        lines.append(f"- summary: {checklist.get('summary')}")
        lines.append(f"- basis: {checklist.get('basis')}")
        lines.append("- items:")
        for item in checklist.get("items", []):
            lines.append(f"  - {item}")

        return "\n".join(lines)
