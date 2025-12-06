"""
perception.py — Updated Perception Module (v3 ERORLL-Aligned)
-------------------------------------------------------------
Fully aligned with the NEW PerceptionSnapshot schema:

PerceptionSnapshot fields:
    entities: List[str]
    intent: Optional[str]
    constraints: List[str]
    original_goal_achieved: bool
    local_goal_achieved: bool
    reasoning: str
    local_reasoning: str
    missing_parameters: List[str]
    result_requirement: str
    solution_summary: str
    confidence: float

This module:
- Sends perception prompt + JSON input to Gemini
- Extracts strictly the JSON returned
- Normalizes it EXACTLY to PerceptionSnapshot schema
- Provides strong fallback recovery
"""

import json
from pathlib import Path
import os
from typing import Any, Dict

from google import genai
from google.genai.errors import ServerError

from agent.perception_snapshot import PerceptionSnapshot
from dotenv import load_dotenv

load_dotenv()


class Perception:
    """
    Perception engine that returns clean ERORLL JSON snapshots.
    """

    def __init__(self, perception_prompt_path: str, api_key: str | None = None,
                 model: str = "gemini-2.0-flash"):

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")

        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.prompt_template = Path(perception_prompt_path).read_text(encoding="utf-8")

    # =============================================================
    # PUBLIC ENTRY
    # =============================================================
    def run(self, p_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs perception → returns an ERORLL JSON dict matching PerceptionSnapshot.
        """

        prompt = (
            self.prompt_template.strip()
            + "\n\nReturn ONLY the ERORLL JSON.\n\n"
            + "```json\n"
            + json.dumps(p_input, indent=2)
            + "\n```"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            raw = response.text.strip()

        except ServerError as e:
            print(f"❌ Perception LLM Error: {e}")
            return self._fallback_snapshot(str(e))

        # Extract JSON (strict)
        parsed = self._extract_json(raw)
        if parsed is None:
            print("⚠️ Perception JSON malformed — attempting salvage")
            parsed = self._salvage_json(raw)

        # Normalize into PerceptionSnapshot dict
        normalized = self._normalize_snapshot(parsed)
        return normalized

    # =============================================================
    # JSON EXTRACTION
    # =============================================================
    def _extract_json(self, text: str) -> Dict[str, Any] | None:
        """
        Extract strictly the first { ... } block.
        """

        # Remove ``` fences if present
        if text.startswith("```"):
            try:
                cleaned = text.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                return json.loads(cleaned)
            except Exception:
                pass

        # direct JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # extract { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                return None

        return None

    # =============================================================
    # SALVAGE FOR BROKEN JSON
    # =============================================================
    def _salvage_json(self, text: str) -> Dict[str, Any]:
        """
        Minimal ERORLL fallback to avoid crashes.
        """

        return {
            "entities": [],
            "intent": "",
            "constraints": [],
            "original_goal_achieved": False,
            "local_goal_achieved": False,
            "reasoning": "Perception failed to parse JSON.",
            "local_reasoning": "",
            "missing_parameters": [],
            "result_requirement": "Unable to parse",
            "solution_summary": "",
            "confidence": 0.0,
        }

    # =============================================================
    # SNAPSHOT NORMALIZATION
    # =============================================================
    def _normalize_snapshot(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Forces EXACT PerceptionSnapshot schema.
        """

        defaults = {
            "entities": [],
            "intent": "",
            "constraints": [],
            "original_goal_achieved": False,
            "local_goal_achieved": False,
            "reasoning": "",
            "local_reasoning": "",
            "missing_parameters": [],
            "result_requirement": "",
            "last_tooluse_summary":"none",
            "solution_summary": "",
            "confidence": 0.0
        }

        snapshot = {k: raw.get(k, defaults[k]) for k in defaults}

        # guarantee correct types
        if not isinstance(snapshot["entities"], list):
            snapshot["entities"] = []
        if not isinstance(snapshot["constraints"], list):
            snapshot["constraints"] = []
        if not isinstance(snapshot["missing_parameters"], list):
            snapshot["missing_parameters"] = []

        # ensure booleans
        snapshot["original_goal_achieved"] = bool(snapshot["original_goal_achieved"])
        snapshot["local_goal_achieved"] = bool(snapshot["local_goal_achieved"])

        # ensure numeric
        try:
            snapshot["confidence"] = float(snapshot["confidence"])
        except Exception:
            snapshot["confidence"] = 0.0

        return snapshot

    # =============================================================
    # FALLBACK SNAPSHOT
    # =============================================================
    def _fallback_snapshot(self, error: str) -> Dict[str, Any]:
        return {
            "entities": [],
            "intent": "",
            "constraints": [],
            "original_goal_achieved": False,
            "local_goal_achieved": False,
            "reasoning": f"Perception error: {error}",
            "local_reasoning": "",
            "missing_parameters": [],
            "result_requirement": "LLM failure",
            "solution_summary": "",
            "confidence": 0.0,
        }
