"""
decision.py — Strategy-Aware DAG Planner (v4 stable)
-----------------------------------------------------
Uses OFFICIAL Gemini Python SDK (google.genai)

Fixes:
- remove symbolic parents
- propagate planning_strategy consistently
- safe UUID node assignment
- robust JSON extraction
"""
import json
import traceback
import os
import uuid
from typing import Any, Dict

from agent.step import StepType
from google import genai
from google.genai.errors import ServerError

#from asyncio import tools


class Decision:

    def __init__(self, prompt_path: str, multi_mcp: Any):

        self.multi_mcp = multi_mcp

        # Load planner prompt
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

        # Initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment.")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"

    # ==========================================================
    # MAIN ENTRY
    # ==========================================================
    def run(self, planning_context: Dict[str, Any]) -> Dict[str, Any]:

        # Guarantee strategy always present
        planning_context.setdefault("planning_strategy", "adaptive")

        prompt = self._build_prompt(planning_context)

        print("********************************")
        print(prompt)
        print("********************************")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            raw_text = response.text.strip()
            print("Decision Raw:", raw_text)

        except ServerError as e:
            print("❗ Decision model server error:", e)
            return self._default_conclusion(planning_context)

        # ---- Try parsing JSON ----
        try:
            parsed = self._parse_llm_output(raw_text)
        except Exception:
            print("❗ Decision JSON parsing failed — fallback triggered.")
            print(traceback.format_exc())
            return self._default_conclusion(planning_context)

        # ---- Normalize DAG ----
        normalized = self._normalize_planner_output(parsed, planning_context)
        normalized["raw_text"] = raw_text[:2000]

        return normalized

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================
    def _build_prompt(self, ctx: Dict[str, Any]) -> str:
        tools = ctx.get("tools_available", [])
        ctx["tools_available"] = tools
        return self.prompt_template + "\n\n" + json.dumps(ctx, indent=2)

    # ==========================================================
    # JSON PARSER
    # ==========================================================
    def _parse_llm_output(self, txt: str) -> Dict[str, Any]:

        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            pass

        # ```json blocks
        if txt.startswith("```"):
            stripped = txt.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # extract { ... }
        start = txt.find("{")
        end = txt.rfind("}")
        if start != -1 and end != -1:
            inner = txt[start:end + 1]
            return json.loads(inner)

        raise ValueError("No valid JSON found in LLM output.")

    # ==========================================================
    # NODE NORMALIZER
    # ==========================================================
    def _normalize_node(self, node_json: Dict[str, Any]) -> Dict[str, Any]:

        new_id = str(uuid.uuid4())

        step_type = node_json.get("type", "CODE").upper()
        if step_type not in StepType.__members__:
            step_type = "CODE"

        # ❗ Parents removed (symbolic names cause graph errors)
        return {
            "id": new_id,
            "type": step_type,
            "description": node_json.get("description", "No description provided."),
            "parents": [],                                 # always empty
            "tool_name": node_json.get("tool_name"),
            "tool_args": node_json.get("tool_args"),
            "code": node_json.get("code"),
            "prompt": node_json.get("prompt"),
            "input_context": node_json.get("input_context"),
            "question": node_json.get("question"),
            "conclusion": node_json.get("conclusion"),
        }

    # ==========================================================
    # PLANNER OUTPUT NORMALIZATION
    # ==========================================================
    def _normalize_planner_output(self, parsed: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:

        # strategy propagation
        strategy = parsed.get("planning_strategy") or ctx.get("planning_strategy") or "adaptive"

        # CASE A — full DAG
        if "plan_graph" in parsed and "nodes" in parsed["plan_graph"]:
            return {
                "plan_text": parsed.get("plan_text", []),
                "planning_strategy": strategy,
                "plan_graph": {
                    "nodes": [self._normalize_node(n) for n in parsed["plan_graph"]["nodes"]]
                }
            }

        # CASE B — single node
        single = self._normalize_node(parsed)
        return {
            "plan_text": parsed.get("plan_text", ["Single-step plan"]),
            "planning_strategy": strategy,
            "plan_graph": {"nodes": [single]},
        }

    # ==========================================================
    # FALLBACK
    # ==========================================================
    def _default_conclusion(self, ctx: Dict[str, Any]):
        return {
            "plan_text": ["Planner fallback: returning safe answer"],
            "planning_strategy": ctx.get("planning_strategy", "adaptive"),
            "plan_graph": {
                "nodes": [
                    {
                        "id": "fail_safe_conclude",
                        "type": "CONCLUDE",
                        "description": "LLM failed, using fallback conclusion.",
                        "parents": [],
                        "conclusion": "I could not generate a structured plan."
                    }
                ]
            }
        }
