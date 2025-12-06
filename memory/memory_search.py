"""
memory_search.py — Stable Memory Recall Engine (v3)
---------------------------------------------------

Responsibilities:
- Scan memory/session_logs/*.json
- Extract content relevant to the user query
- Return normalized, LLM-friendly snippets
- Never raise exceptions (safe failure)
- Avoid noise, repeated entries, or irrelevant matches
"""

import os
import json
import re
from pathlib import Path


class MemorySearch:

    def __init__(self, memory_dir: str = None):
        # Default folder
        self.memory_dir = memory_dir or "memory/session_logs"
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)

    # =======================================================================
    # PUBLIC API
    # =======================================================================
    def search_memory(self, query: str):
        """
        Main entry point called by AgentLoop.

        Returns:
        [
            {
                "source": "file_name.json",
                "match_score": <float>,
                "content": <string>
            },
            ...
        ]
        """

        results = []

        # Load *.json memory files
        try:
            files = list(Path(self.memory_dir).glob("*.json"))
        except Exception:
            return []

        if not files:
            return []

        # Tokenize query minimally
        query_tokens = self._tokenize(query)

        # ---------------------------------------------------------------
        # Search through logs
        # ---------------------------------------------------------------
        for file_path in files:
            data = self._safe_load_json(file_path)
            if not data:
                continue

            # extract content field or fallback
            content = data.get("response") or data.get("answer") or json.dumps(data)

            # compute simple lexical relevance
            score = self._score_text(content, query_tokens)
            if score <= 0:
                continue

            snippet = self._extract_snippet(content, query_tokens)

            if snippet:
                results.append({
                    "source": file_path.name,
                    "match_score": score,
                    "content": snippet
                })

        # sort by relevance descending
        results.sort(key=lambda x: x["match_score"], reverse=True)

        # Keep top 5 to avoid LLM overload
        return results[:5]

    # =======================================================================
    # Internal Helper Methods
    # =======================================================================

    def _tokenize(self, text: str):
        """
        Simple lowercase alphanumeric tokenization.
        """
        text = text.lower()
        return re.findall(r"[a-zA-Z0-9]+", text)

    def _safe_load_json(self, file_path: Path):
        """
        Safely load JSON without crashing the agent.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _score_text(self, text: str, tokens: list[str]) -> float:
        """
        Lexical match score = number of matched tokens.
        """
        if not text:
            return 0

        text_l = text.lower()
        score = 0
        for t in tokens:
            if t in text_l:
                score += 1
        return float(score)

    def _extract_snippet(self, text: str, tokens: list[str]) -> str:
        """
        Extracts a short context snippet where query tokens appear.
        """

        if not text:
            return ""

        text_l = text.lower()

        # Find first matching token
        first_hit = None
        for t in tokens:
            idx = text_l.find(t)
            if idx != -1:
                first_hit = idx
                break

        # No match
        if first_hit is None:
            return ""

        # Extract a window around the match
        start = max(0, first_hit - 80)
        end = min(len(text), first_hit + 200)
        snippet = text[start:end]

        # Normalize whitespace
        snippet = re.sub(r"\s+", " ", snippet).strip()

        return snippet if snippet else ""
