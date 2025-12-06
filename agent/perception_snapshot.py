from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PerceptionSnapshot:
    # Extracted entities and intent
    entities: List[str]
    intent: Optional[str]
    constraints: List[str]

    # Missing info
    missing_parameters: List[str]

    # Type of result the user expects
    result_requirement: str

    # Goal state flags
    original_goal_achieved: bool
    local_goal_achieved: bool

    # Reasoning summaries
    reasoning: str
    local_reasoning: str

    # Tool summary (success or failure)
    last_tooluse_summary: str

    # If goal achieved → final answer, else → "Not ready yet"
    solution_summary: str

    # Confidence float 0.0–1.0
    confidence: float

    def to_dict(self):
        return self.__dict__
