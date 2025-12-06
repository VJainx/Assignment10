from dataclasses import dataclass, field
from typing import Dict, List, Optional
from agent.step import Step, StepStatus


@dataclass
class PlanNode:
    node_id: str
    step: Step
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "parents": self.parents[:],
            "children": self.children[:],
            "status": self.status.value,
            "step": self.step.to_dict(),
        }


class PlanGraph:

    def __init__(self):
        self.nodes: Dict[str, PlanNode] = {}
        self.root_ids: List[str] = []


    # ======================================================
    # from_json() — REQUIRED BY NEW AGENT LOOP
    # ======================================================
    @classmethod
    def from_json(cls, plan_graph_json: dict):
        """
        Planner JSON:
        {
            "nodes": [
                {
                    "id": "...",
                    "type": "...",
                    "description": "...",
                    "parents": [...],
                    "tool_name": "...",
                    "tool_args": {...},
                    "code": "...",
                    "prompt": "...",
                    "input_context": "...",
                    "question": "...",
                    "conclusion": "..."
                }
            ]
        }
        """
        pg = cls()
        node_list = plan_graph_json.get("nodes", [])

        # --- First pass: create PlanNode objects
        for n in node_list:

            step = Step(
                description=n.get("description", ""),
                step_type=n.get("type", "CODE"),
                tool_name=n.get("tool_name"),
                tool_args=n.get("tool_args"),
                code=n.get("code"),
                llm_prompt=n.get("prompt"),
                llm_input_context=n.get("input_context"),
                user_question=n.get("question"),
                conclusion=n.get("conclusion"),
            )

            node_id = n["id"]
            pg.nodes[node_id] = PlanNode(
                node_id=node_id,
                step=step,
                parents=[],
                children=[],
                status=StepStatus.PENDING
            )

        # --- Second pass: link parents/children
        for n in node_list:
            nid = n["id"]
            parents = n.get("parents", [])

            pg.nodes[nid].parents = parents

            for p in parents:
                if p in pg.nodes:
                    pg.nodes[p].children.append(nid)

        # compute root_ids
        pg.root_ids = [nid for nid, node in pg.nodes.items() if not node.parents]

        return pg


    # ======================================================
    # ADD NODE (first pass)
    # ======================================================
    def add_step(self, step: Step, parents: List[str] = None) -> str:
        parents = parents or []

        node_id = step.step_id
        node = PlanNode(node_id=node_id, step=step, parents=parents)

        self.nodes[node_id] = node

        if not parents:
            if node_id not in self.root_ids:
                self.root_ids.append(node_id)

        return node_id


    # ======================================================
    # set real parents (used in patched DAG)
    # ======================================================
    def set_parents(self, node_id: str, parent_ids: List[str]):
        node = self.nodes[node_id]
        node.parents = []

        for p in parent_ids:
            if p not in self.nodes:
                print(f"[PlanGraph] WARNING: Missing parent: {p}")
                continue

            node.parents.append(p)

            if node_id not in self.nodes[p].children:
                self.nodes[p].children.append(node_id)

        self._recompute_roots()


    def _recompute_roots(self):
        self.root_ids = [nid for nid, n in self.nodes.items() if not n.parents]


    # ======================================================
    # ACCESS
    # ======================================================
    def get_node(self, node_id: str) -> PlanNode:
        return self.nodes[node_id]


    # ======================================================
    # Status
    # ======================================================
    def mark_node_complete(self, node_id: str):
        self.nodes[node_id].status = StepStatus.COMPLETED

    def mark_node_failed(self, node_id: str):
        self.nodes[node_id].status = StepStatus.FAILED


    # ======================================================
    # EXECUTION LOGIC
    # ======================================================
    def next_runnable_node(self) -> Optional[PlanNode]:
        """
        A node is runnable if:
        - status == PENDING
        - all parents COMPLETED
        """
        for nid, node in self.nodes.items():
            if node.status != StepStatus.PENDING:
                continue

            if all(self.nodes[p].status == StepStatus.COMPLETED for p in node.parents):
                return node

        return None


    # ======================================================
    # Insert patch nodes (mid-session replanning)
    # ======================================================
    def insert_patch_nodes_old(self, patch_nodes: List[dict]):
        """
        patch_nodes: list of planner JSON nodes (exact same schema as initial planning)
        """
        for n in patch_nodes:

            nid = n["id"]

            step = Step(
                description=n.get("description", ""),
                step_type=n.get("type", "CODE"),
                tool_name=n.get("tool_name"),
                tool_args=n.get("tool_args"),
                code=n.get("code"),
                llm_prompt=n.get("prompt"),
                llm_input_context=n.get("input_context"),
                user_question=n.get("question"),
                conclusion=n.get("conclusion"),
            )

            if nid not in self.nodes:
                self.nodes[nid] = PlanNode(
                    node_id=nid,
                    step=step,
                    parents=[],
                    children=[],
                    status=StepStatus.PENDING,
                )

            parents = n.get("parents", [])
            self.set_parents(nid, parents)

    def _recompute_all_parent_child_links(self, nodes_json):
        # clear existing child lists
        for node in self.nodes.values():
            node.children = []

        # rebuild parent→child relationships
        for node_json in nodes_json:
            node_id = node_json["id"]
            parents = node_json.get("parents", [])

            for p in parents:
                if p in self.nodes:
                    self.nodes[node_id].parents.append(p)
                    self.nodes[p].children.append(node_id)

        self._recompute_roots()

    def insert_patch_nodes_old1(self, patch_nodes):
        """
        Patch new nodes from the planner into the graph.
        Preserves real PlanNode structure.
        """
        for node_json in patch_nodes:

            # Always normalize step through Step.from_json()
            step = Step.from_json(node_json)

            node_id = step.step_id

            # Create PlanNode if missing
            if node_id not in self.nodes:
                self.nodes[node_id] = PlanNode(
                    node_id=node_id,
                    step=step,
                    parents=[],
                    children=[],
                    status=StepStatus.PENDING
                )
            else:
                # Update its step but keep structure
                self.nodes[node_id].step = step

        # --------------------------------------------------------
        # Second pass — apply parent/child wiring
        # --------------------------------------------------------
        for node_json in patch_nodes:
            node_id = node_json["id"]
            parents = node_json.get("parents", [])

            self.nodes[node_id].parents = parents

            for p in parents:
                if p in self.nodes:
                    if node_id not in self.nodes[p].children:
                        self.nodes[p].children.append(node_id)

        self._recompute_roots()

    def insert_patch_nodes(self, patch_nodes):
        """
        Insert new nodes returned by mid-session replanning.

        patch_nodes is a list of normalized planner node dicts.
        """

        # -------------------------------
        # PASS 1 — Create all PlanNodes
        # -------------------------------
        for node_json in patch_nodes:
            node_id = node_json["id"]

            # Create Step object
            step = Step.from_json(node_json)

            # Insert NEW PlanNode
            if node_id not in self.nodes:
                self.nodes[node_id] = PlanNode(
                    node_id=node_id,
                    step=step,
                    parents=[],
                    children=[],
                    status=StepStatus.PENDING
                )

        # -------------------------------
        # PASS 2 — Assign parents/children
        # -------------------------------
        for node_json in patch_nodes:
            node_id = node_json["id"]
            parent_ids = node_json.get("parents", [])

            node = self.nodes[node_id]
            node.parents = []   # reset

            for pid in parent_ids:
                if pid not in self.nodes:
                    print(f"[PlanGraph] WARNING: Parent {pid} not found during patch insertion")
                    continue

                node.parents.append(pid)

                # Link child to parent
                if node_id not in self.nodes[pid].children:
                    self.nodes[pid].children.append(node_id)

        # -------------------------------
        # Recompute roots
        # -------------------------------
        self._recompute_roots()


    # ======================================================
    # Serialization
    # ======================================================
    def to_dict(self):
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "root_ids": self.root_ids[:],
        }
    
    def to_serializable_dict_out(self):
        out = {"nodes": {}, "root_ids": list(self.root_ids)}
        for nid, node in self.nodes.items():
            node_dict = node.to_dict()

            # Deep sanitize step.execution_result for every node
            step_dict = node_dict["step"]
            if isinstance(step_dict.get("execution_result"), object):
                try:
                    if hasattr(step_dict["execution_result"], "to_dict"):
                        step_dict["execution_result"] = step_dict["execution_result"].to_dict()
                    elif not isinstance(step_dict["execution_result"], (dict, list, str, int, float, bool, type(None))):
                        step_dict["execution_result"] = str(step_dict["execution_result"])
                except:
                    step_dict["execution_result"] = str(step_dict["execution_result"])

            out["nodes"][nid] = node_dict

        return out
    
    import json

    def to_serializable_dict(self):
        out = {"nodes": {}, "root_ids": list(self.root_ids)}

        for nid, node in self.nodes.items():
            node_dict = node.to_dict()

            step = node_dict["step"]

            # ---- SANITIZE execution_result ----
            er = step.get("execution_result")
            if er is not None:
                # Already dict/list/primitive? Keep it.
                if isinstance(er, (dict, list, str, int, float, bool)) or er is None:
                    pass
                # Has a to_dict() method?
                elif hasattr(er, "to_dict"):
                    step["execution_result"] = er.to_dict()
                # Fallback: convert to string
                else:
                    step["execution_result"] = str(er)

            out["nodes"][nid] = node_dict

        return out


