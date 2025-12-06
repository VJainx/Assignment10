"""
AgentSession (Graph-Native)
---------------------------
Manages the state of a full agent reasoning session.

This version removes all linear-step planning artifacts and now
reflects the new PlanGraph DAG architecture.

Stores:
- session metadata
- PlanGraph (DAG)
- perception snapshots
- correctness/debug trace
- final answer and confidence
"""

import time
from typing import Optional, List, Dict, Any
from planning.plan_graph import PlanGraph
from perception_snapshot import PerceptionSnapshot


class AgentSession:

    def __init__(self, session_id: str, query: str):
        self.session_id = session_id
        self.original_query = query

        # The plan graph (multi-node DAG of reasoning steps)
        self.plan_graph = PlanGraph()

        # Final output
        self.final_answer: Optional[str] = None
        self.final_confidence: float = 0.0

        # Perception
        self.initial_perception: Optional[PerceptionSnapshot] = None

        # Debug trace for live view or logs
        self.trace: List[str] = []

        # Timestamp
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    # --------------------------------------------------------------
    # Logging / Debugging
    # --------------------------------------------------------------
    def record(self, message: str):
        print(message)
        self.trace.append(message)

    # --------------------------------------------------------------
    # Finalization
    # --------------------------------------------------------------
    def mark_complete(self, answer: str, confidence: float):
        self.final_answer = answer
        self.final_confidence = confidence
        self.end_time = time.time()

    # --------------------------------------------------------------
    # JSON Export
    # --------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query": self.original_query,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "final_answer": self.final_answer,
            "final_confidence": self.final_confidence,
            "initial_perception": (
                self.initial_perception.to_dict()
                if self.initial_perception else None
            ),
            "plan_graph": self.plan_graph.to_dict(),
            "trace": self.trace
        }

    # --------------------------------------------------------------
    # Pretty-print DAG Summary
    # --------------------------------------------------------------
    def summary(self) -> str:
        lines = []
        lines.append(f"Session ID: {self.session_id}")
        lines.append(f"Query: {self.original_query}")
        lines.append("")

        if self.final_answer:
            lines.append("=== FINAL ANSWER ===")
            lines.append(self.final_answer)
            lines.append(f"(confidence: {self.final_confidence})")
        else:
            lines.append("=== No Final Answer ===")

        lines.append("\n=== PLAN GRAPH ===")
        for node_id, node in self.plan_graph.nodes.items():
            s = node.step
            lines.append(
                f"[{node_id}] {s.step_type.name} | status={node.status.value}"
            )
            lines.append(f"  description: {s.description}")
            if s.execution_result:
                lines.append(f"  result: {s.execution_result}")
            if s.conclusion:
                lines.append(f"  conclusion: {s.conclusion}")
            lines.append("")
        return "\n".join(lines)
