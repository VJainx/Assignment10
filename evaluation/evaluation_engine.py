"""
evaluation_engine.py — Execution Evaluation Layer (v3 ERORLL)
--------------------------------------------------------------
Evaluates the output of a single step and determines:

- global_success:        Final answer found → Agent should END
- needs_replan:          The step failed or perception says “missing info”
- final_answer:          Filled only if global_success is true
- reasoning:             Freeform reasoning for debug

Input:
- Step object
- execution_result (dict from ExecutionEngine)
- perception (PerceptionSnapshot)

Output:
{
    "global_success": bool,
    "needs_replan": bool,
    "final_answer": str | None,
    "reasoning": str
}
"""

from typing import Any, Dict
from agent.step import Step, StepType
from agent.perception_snapshot import PerceptionSnapshot


class EvaluationResult:
    """
    Simple container for evaluation results.
    """
    def __init__(
        self,
        global_success: bool,
        needs_replan: bool,
        final_answer: str | None,
        reasoning: str
    ):
        self.global_success = global_success
        self.needs_replan = needs_replan
        self.final_answer = final_answer
        self.reasoning = reasoning

    def to_dict(self):
        return {
            "global_success": self.global_success,
            "needs_replan": self.needs_replan,
            "final_answer": self.final_answer,
            "reasoning": self.reasoning,
        }


class EvaluationEngine:
    """
    Evaluates perception outcome + execution result
    to determine "conclude / continue / replan".
    """

    # ===========================================================
    # Main evaluation entry
    # ===========================================================
    def evaluate(
        self,
        step: Step,
        exec_result: Dict[str, Any] | None,
        perception: PerceptionSnapshot
    ) -> EvaluationResult:

        # Safety: execution missing / crashed
        if exec_result is None:
            return EvaluationResult(
                global_success=False,
                needs_replan=True,
                final_answer=None,
                reasoning="Execution produced no result."
            )
        
        # -----------------------------------------------------------
        # SPECIAL RULE:
        # LLM_CALL should NOT cause REPLAN due to missing_parameters
        # unless the execution itself had an error.
        # -----------------------------------------------------------
        is_llm_call = step.step_type == StepType.LLM_CALL
        exec_failed = ("error" in str(exec_result).lower())

        # If this is an LLM_CALL and execution DID NOT fail:
        if is_llm_call and not exec_failed:
            # ignore missing_parameters → treat as normal progression
            perception.missing_parameters = []

        # ===========================================================
        # CASE 1 — CONCLUDE step
        # ===========================================================
        if step.step_type == StepType.CONCLUDE:
            return EvaluationResult(
                global_success=True,
                needs_replan=False,
                final_answer=step.conclusion,
                reasoning="Conclude step executed."
            )

        # ===========================================================
        # CASE 2 — ASK_USER always pauses and demands replan
        # ===========================================================
        if step.step_type == StepType.ASK_USER:
            return EvaluationResult(
                global_success=False,
                needs_replan=True,
                final_answer=None,
                reasoning="ASK_USER step returns control to user; replanning required."
            )

        # ===========================================================
        # CASE 3 — TOOL / CODE / LLM_CALL success/failure
        # ===========================================================
        engine_success = exec_result.get("success", False)

        if not engine_success:
            # Hard execution failure -> replan
            return EvaluationResult(
                global_success=False,
                needs_replan=True,
                final_answer=None,
                reasoning=f"Execution failure: {exec_result.get('error')}"
            )

        # ===========================================================
        # CASE 4 — Check perception of the result
        # ===========================================================

        # Path A: perception says we achieved global goal
        if perception.original_goal_achieved:
            return EvaluationResult(
                global_success=True,
                needs_replan=False,
                final_answer=perception.solution_summary or "Answer derived.",
                reasoning="Perception indicates original goal is fully satisfied."
            )

        # Path B: local goal achieved but not global → continue executing DAG
        if perception.local_goal_achieved:
            return EvaluationResult(
                global_success=False,
                needs_replan=False,
                final_answer=None,
                reasoning="Perception indicates local goal complete; continue."
            )

        # Path C: missing parameters → requires REPLAN
        if perception.missing_parameters and step.step_type != StepType.LLM_CALL:
            return EvaluationResult(
                global_success=False,
                needs_replan=True,
                final_answer=None,
                reasoning="Perception indicates missing parameters for progress."
            )

        # Path D: No progress → REPLAN
        if not perception.reasoning and not perception.solution_summary:
            return EvaluationResult(
                global_success=False,
                needs_replan=True,
                final_answer=None,
                reasoning="Perception provided no actionable progress → replan."
            )

        # Path E: General progression → continue DAG
        return EvaluationResult(
            global_success=False,
            needs_replan=False,
            final_answer=None,
            reasoning="Normal progression; next node required."
        )
