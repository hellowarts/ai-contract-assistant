import sys

from core.workflow_engine import WorkflowEngine
from core.workflow_state import WorkflowState


def run_workflow() -> WorkflowState:

    try:

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    except Exception:

        pass

    engine = WorkflowEngine()

    text = input("계약 내용을 입력하세요.\n> ")

    state = engine.run(text)

    print()
    print(state.outputs.get("final_output", ""))

    return state


def main() -> None:

    run_workflow()


if __name__ == "__main__":

    main()