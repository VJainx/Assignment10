"""
TaskSpec — Structured representation of the initial user query.
Used by the planner to produce better plans.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class TaskSpec:
    intent: str
    entities: List[str]
    constraints: Dict[str, Any]
    missing_parameters: List[str]
    expected_output: str
    solvable_with_memory: bool
    solvable_with_tools: bool
    solvable_directly: bool

    def to_dict(self):
        return {
            "intent": self.intent,
            "entities": self.entities,
            "constraints": self.constraints,
            "missing_parameters": self.missing_parameters,
            "expected_output": self.expected_output,
            "solvable_with_memory": self.solvable_with_memory,
            "solvable_with_tools": self.solvable_with_tools,
            "solvable_directly": self.solvable_directly,
        }
