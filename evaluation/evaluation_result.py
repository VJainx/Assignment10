# evaluation/evaluation_result.py

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class EvaluationResult:
    local_success: bool
    global_success: bool
    final_answer: Optional[str]
    reasoning: str
    needs_replan: bool = False
