from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, Dict
import uuid


class StepType(Enum):
    TOOL = auto()
    CODE = auto()
    LLM_CALL = auto()
    ASK_USER = auto()
    CONCLUDE = auto()


class StepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    # Unique ID required by PlanGraph
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Standard agent fields
    description: str = ""
    step_type: StepType = StepType.CODE
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0

    # TOOL fields
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None

    # CODE fields
    code: Optional[str] = None

    # LLM fields
    llm_prompt: Optional[str] = None
    llm_input_context: Optional[str] = None

    # ASK_USER fields
    user_question: Optional[str] = None

    # CONCLUDE fields
    conclusion: Optional[str] = None

    # Execution + perception output
    execution_result: Any = None
    perception_snapshot: Any = None

    def to_dict(self):
        return {
            "step_id": self.step_id,
            "description": self.description,
            "step_type": self.step_type.name,
            "status": self.status.value,
            "attempts": self.attempts,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "code": self.code,
            "llm_prompt": self.llm_prompt,
            "llm_input_context": self.llm_input_context,
            "user_question": self.user_question,
            "conclusion": self.conclusion,
            "execution_result": self.execution_result,
            "perception_snapshot": (
                self.perception_snapshot.to_dict()
                if self.perception_snapshot else None
            ),
        }
    
    @staticmethod
    def from_json_old(data: dict) -> "Step":
        step_type_raw = data.get("type", "CODE")

        # normalize to enum
        if isinstance(step_type_raw, str):
            step_type = StepType[step_type_raw.upper()]
        else:
            step_type = step_type_raw

        return Step(
            description=data.get("description", ""),
            step_type=step_type,
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            code=data.get("code"),
            llm_prompt=data.get("prompt"),
            llm_input_context=data.get("input_context"),
            user_question=data.get("question"),
            conclusion=data.get("conclusion"),
        )
    
    @staticmethod
    def from_json(data: dict):
        raw = data.get("type", "CODE")

        if isinstance(raw, str):
            step_type = StepType[raw.upper()]
        else:
            step_type = raw

        return Step(
            description=data.get("description", ""),
            step_type=step_type,
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            code=data.get("code"),
            llm_prompt=data.get("prompt"),
            llm_input_context=data.get("input_context"),
            user_question=data.get("question"),
            conclusion=data.get("conclusion"),
        )


