from dataclasses import dataclass, field

@dataclass
class WorkflowState:

    header: dict = field(default_factory=dict)

    progress: dict = field(default_factory=dict)

    request: dict = field(default_factory=dict)

    contract: dict = field(default_factory=dict)

    regulation: dict = field(default_factory=dict)

    documents: dict = field(default_factory=dict)

    checklist: dict = field(default_factory=dict)

    outputs: dict = field(default_factory=dict)

    evidence: list = field(default_factory=list)

    actions: list = field(default_factory=list)

    logs: list = field(default_factory=list)