"""
agent_loop2.py — Graph-Native Agent Orchestrator (v3 ERORLL)
-------------------------------------------------------------
Fully aligned with:
- Perception v3 (ERORLL snapshots)
- Planner v3 (initial + mid-session replanning)
- ExecutionEngine v3
- EvaluationEngine v3
- PlanGraph v3

This version replaces all legacy logic and ensures:
- correct DAG traversal
- correct perception lifecycle
- proper mid-session replanning
- strict replan limit
"""

import uuid
from typing import Optional, Dict, Any

from planning.plan_graph import PlanGraph
from perception.perception import Perception
from memory.memory_search import MemorySearch
from decision.decision import Decision
from execution.execution_engine import ExecutionEngine
from evaluation.evaluation_engine import EvaluationEngine
from agent.perception_snapshot import PerceptionSnapshot
from agent.step import Step, StepType


# =====================================================================
# AgentSession — holds query, plan graph, and final results
# =====================================================================
class AgentSession:
    def __init__(self, session_id: str, query: str):
        self.session_id = session_id
        self.original_query = query

        self.plan_graph = PlanGraph()
        self.initial_perception: Optional[PerceptionSnapshot] = None

        self.final_answer: Optional[str] = None
        self.final_confidence: float = 0.0

        self.last_execution: Optional[dict] = None
        self.last_perception: Optional[PerceptionSnapshot] = None

        self.replan_attempts = 0
        self.debug_trace = []

    def record(self, msg: str):
        print(msg)
        self.debug_trace.append(msg)


# =====================================================================
# AgentContext — dependency container
# =====================================================================
class AgentContext:
    def __init__(self, perception, planner, memory, executor, evaluator):
        self.perception = perception
        self.planner = planner
        self.memory = memory
        self.executor = executor
        self.evaluator = evaluator


# =====================================================================
# Main Agent Loop
# =====================================================================
class AgentLoop:

    def __init__(self,
                 perception_prompt_path,
                 decision_prompt_path,
                 multi_mcp,
                 strategy="adaptive"):

        self.strategy = strategy
        self.max_replans = 3

        self.ctx = AgentContext(
            perception=Perception(perception_prompt_path),
            planner=Decision(decision_prompt_path, multi_mcp),
            memory=MemorySearch(),
            executor=ExecutionEngine(multi_mcp),
            evaluator=EvaluationEngine(),
        )

    # ===============================================================
    async def run(self, user_query: str) -> AgentSession:

        session = AgentSession(session_id=str(uuid.uuid4()), query=user_query)

        # -----------------------------------------------------------
        # 1. INITIAL PERCEPTION
        # -----------------------------------------------------------
        perception_input = {
            "snapshot_type": "user_query",
            "text": user_query,
        }

        raw_snapshot = self.ctx.perception.run(perception_input)
        perception = PerceptionSnapshot(**raw_snapshot)

        session.initial_perception = perception
        session.record("[Perception] Completed initial perception.")

        if perception.original_goal_achieved:
            session.record("[Agent] Goal solved at perception stage.")
            return self._finish(session, perception.solution_summary, perception.confidence)

        # -----------------------------------------------------------
        # 2. INITIAL PLANNING
        # -----------------------------------------------------------
        plan_output = self.ctx.planner.run({
            "plan_mode": "initial",
            "planning_strategy": self.strategy,
            "original_query": user_query,
            "perception": perception.to_dict(),
            "current_plan_graph": None,
            "failed_node": None,
            "last_step": None,
        })

        #session.plan_graph = PlanGraph.from_json(plan_output["plan_graph"])
        self._planner_output_to_graph(session, plan_output)

        # -----------------------------------------------------------
        # MAIN LOOP
        # -----------------------------------------------------------
        while True:

            next_node = session.plan_graph.next_runnable_node()

            if next_node is None:
                return self._finish(session, "No runnable nodes left.", 0.3)

            step: Step = next_node.step
            #session.record(f"[Execution] Running {next_node.id} ({step.step_type.name})")
            session.record(f"[Execution] Running {next_node.node_id} ({step.step_type.name})")


            # -------------------------------------------------------
            # 3. EXECUTION
            # -------------------------------------------------------
            exec_result_raw = await self._execute_step(step)
            exec_result = self._normalize_exec_result(exec_result_raw)
            session.last_execution = exec_result

            # -------------------------------------------------------
            # 4. PERCEPTION FOR STEP RESULT
            # -------------------------------------------------------
            perception_input = {
                "snapshot_type": "step_result",
                "original_query": user_query,
                "step_id": next_node.node_id,
                "step_type": step.step_type.name,
                "step_output": exec_result,
                #"plan_graph": session.plan_graph.to_dict(),
                "plan_graph": session.plan_graph.to_serializable_dict(),

            }

            raw_step_snapshot = self.ctx.perception.run(perception_input)
            step_perception = PerceptionSnapshot(**raw_step_snapshot)
            session.last_perception = step_perception

            # -------------------------------------------------------
            # 5. EVALUATION
            # -------------------------------------------------------
            eval_result = self.ctx.evaluator.evaluate(
                step=step,
                exec_result=exec_result,
                perception=step_perception
            )

            # FINAL ANSWER
            if eval_result.global_success:
                return self._finish(session,
                                    eval_result.final_answer,
                                    step_perception.confidence)

            # CONTINUE (no replan)
            if not eval_result.needs_replan:
                session.plan_graph.mark_node_completed(next_node.node_id)
                continue

            # -------------------------------------------------------
            # 6. MID-SESSION REPLANNING
            # -------------------------------------------------------
            session.replan_attempts += 1
            if session.replan_attempts > self.max_replans:
                return self._finish(session, "Too many replans.", 0.4)

            session.record("[Replan] Required.")

            replan = self.ctx.planner.run({
                "plan_mode": "mid_session",
                "planning_strategy": self.strategy,
                "original_query": user_query,
                "current_plan_graph": session.plan_graph.to_dict(),
                "failed_node": next_node.node_id,
                "perception": step_perception.to_dict(),
                "last_step": {
                    "step": next_node.to_dict(),
                    "exec_result": exec_result,
                    "perception": step_perception.to_dict()
                }
            })

            # Patch new DAG nodes
            session.plan_graph.insert_patch_nodes(replan["plan_graph"]["nodes"])

            # Loop continues — execution resumes on next runnable node

    # ==================================================================
    # EXECUTE A STEP
    # ==================================================================
    async def _execute_step(self, step: Step):

        if step.step_type == StepType.TOOL:
            return await self.ctx.executor.execute_tool(step.tool_name, step.tool_args)

        if step.step_type == StepType.CODE:
            return await self.ctx.executor.execute_code(step.code)

        if step.step_type == StepType.LLM_CALL:
            return await self.ctx.executor.execute_llm(step.llm_prompt, step.llm_input_context)

        if step.step_type == StepType.ASK_USER:
            return {"ask_user": step.user_question}

        if step.step_type == StepType.CONCLUDE:
            return {"conclusion": step.conclusion}

        return {"error": "Unknown step type"}

    # ==================================================================
    # FINISH SESSION
    # ==================================================================
    def _finish(self, session: AgentSession, answer: str, confidence: float):
        session.final_answer = answer
        session.final_confidence = confidence
        session.record("[Agent] Session finished.")
        return session
    
    # =========================================================
    # Convert planner node → Step object (ENUM-SAFE)
    # =========================================================
    def _convert_node_to_step(self, node_json: Dict[str, Any]) -> Step:

        # Extract step type as string (planner always outputs string)
        step_type_raw = node_json.get("type", "CODE")

        # Normalize to enum
        if isinstance(step_type_raw, str):
            step_type = StepType[step_type_raw.upper()]
        else:
            step_type = step_type_raw

        return Step(
            description=node_json.get("description", ""),
            step_type=step_type,
            tool_name=node_json.get("tool_name"),
            tool_args=node_json.get("tool_args"),
            code=node_json.get("code"),
            llm_prompt=node_json.get("prompt"),
            llm_input_context=node_json.get("input_context"),
            user_question=node_json.get("question"),
            conclusion=node_json.get("conclusion"),
        )
    
    # =========================================================
# Convert planner DAG → PlanGraph (REQUIRED)
# =========================================================
    def _planner_output_to_graph(self, session, decision_output):
        """
        Takes the planner JSON (nodes with string types)
        and inserts them into the real PlanGraph with proper
        StepType enum conversion and correct parent wiring.
        """

        if "plan_graph" not in decision_output:
            raise ValueError("Planner output missing 'plan_graph'")

        dag_nodes = decision_output["plan_graph"]["nodes"]

        planner_to_real = {}

        # PASS 1 — Create nodes without parents
        for node_json in dag_nodes:
            # convert JSON → Step (this does StepType enum fixing)
            step = Step.from_json(node_json)

            planner_id = node_json["id"]
            real_id = session.plan_graph.add_step(step, parents=[])
            planner_to_real[planner_id] = real_id

        # PASS 2 — Assign parents
        for node_json in dag_nodes:
            planner_id = node_json["id"]
            real_id = planner_to_real[planner_id]

            parent_real_ids = []
            for p in node_json.get("parents", []):
                if p in planner_to_real:
                    parent_real_ids.append(planner_to_real[p])

            session.plan_graph.set_parents(real_id, parent_real_ids)

        return session.plan_graph.root_ids
    
    def _normalize_exec_result(self, result):
        # MCP tool results usually have to_dict()
        if hasattr(result, "to_dict"):
            try:
                return result.to_dict()
            except:
                pass

        # If it already IS JSON-safe
        if isinstance(result, (dict, list, str, int, float, bool, type(None))):
            return result

        # Last-resort fallback
        return str(result)




