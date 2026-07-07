from __future__ import annotations

from typing import Any

from core.workflow_state import WorkflowState


class Supervisor:

    def __init__(self) -> None:

        self.step_order = ["contract", "regulation", "documents", "checklist", "outputs"]

    def next_step(self, state: WorkflowState) -> str | None:

        if not state.contract:

            return "contract"

        if not state.regulation:

            return "regulation"

        if not state.documents:

            return "documents"

        if not state.checklist:

            return "checklist"

        if not state.outputs:

            return "outputs"

        return None

    def is_complete(self, state: WorkflowState) -> bool:

        return self.next_step(state) is None

    def update_progress(self, state: WorkflowState) -> WorkflowState:

        next_step = self.next_step(state)

        completed_steps = [step for step in self.step_order if self._step_is_done(state, step)]

        state.progress = {
            "completed_steps": completed_steps,
            "next_step": next_step,
            "is_complete": next_step is None,
        }

        state.actions.append({
            "agent": "Supervisor",
            "action": "update_progress",
            "next_step": next_step,
        })

        return state

    def _step_is_done(self, state: WorkflowState, step: str) -> bool:

        if step == "contract":

            return bool(state.contract)

        if step == "regulation":

            return bool(state.regulation)

        if step == "documents":

            return bool(state.documents)

        if step == "checklist":

            return bool(state.checklist)

        if step == "outputs":

            return bool(state.outputs)

        return False
