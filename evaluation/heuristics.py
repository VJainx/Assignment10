# evaluation/heuristics.py

from typing import Any
from action.executor import run_user_code  # optional if we evaluate python output
from agent.step import StepType
from execution.execution_result import ExecutionResult


class Heuristics:

    @staticmethod
    def detect_tool_failure(step_type: StepType, exec_result: ExecutionResult) -> bool:
        if step_type == StepType.TOOL and not exec_result.success:
            return True
        return False

    @staticmethod
    def detect_code_failure(step_type: StepType, exec_result: ExecutionResult) -> bool:
        if step_type == StepType.CODE and not exec_result.success:
            return True
        return False

    @staticmethod
    def detect_empty_result(exec_result: ExecutionResult) -> bool:
        if exec_result.data in (None, "", {}):
            return True
        return False

    @staticmethod
    def detect_obvious_answer(exec_result: ExecutionResult) -> bool:
        """
        Simple heuristic: if execution_result returns a dict with `final=True`.
        """
        if isinstance(exec_result.data, dict) and exec_result.data.get("final"):
            return True
        return False
