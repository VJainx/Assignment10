"""
Execution Engine (v3 ERORLL-compatible)
---------------------------------------
Executes TOOL, CODE, and LLM_CALL steps.

Key Features:
- Uses official Google Gemini SDK (google.genai)
- Uniform output schema for all execution modes
- Safe async Python execution sandbox
- Strong error hardening
"""

import traceback
from typing import Any, Dict

from agent.step import Step
from google import genai
from google.genai.errors import ServerError
import os
import asyncio


class ExecutionEngine:

    def __init__(self, multi_mcp):
        self.multi_mcp = multi_mcp

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found for ExecutionEngine")

        self.gemini = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"

    # ===========================================================
    # TOOL EXECUTION
    # ===========================================================
    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any] | None):
        """
        Executes a TOOL step through multi_mcp.
        Normalized unified return format.
        """

        tool_args = tool_args or {}

        if not tool_name:
            return {
                "mode": "tool",
                "success": False,
                "error": "Missing tool name",
                "args": tool_args
            }

        try:
            output = await self.multi_mcp.execute(tool_name, tool_args)
            return {
                "mode": "tool",
                "tool": tool_name,
                "args": tool_args,
                "success": True,
                "output": output
            }

        except Exception as e:
            return {
                "mode": "tool",
                "tool": tool_name,
                "args": tool_args,
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    # ===========================================================
    # CODE EXECUTION
    # ===========================================================
    async def execute_code(self, code: str):
        """
        Executes user code asynchronously in a minimal sandbox.
        """

        if not code or not code.strip():
            return {
                "mode": "code",
                "success": False,
                "error": "Empty code block"
            }

        # Restrict builtins
        sandbox_globals = {
            "__builtins__": {
                "range": range,
                "len": len,
                "min": min,
                "max": max,
                "sum": sum
            }
        }
        sandbox_locals = {}

        try:
            exec(
                "async def __user_fn__():\n" +
                "\n".join(f"    {line}" for line in code.split("\n")),
                sandbox_globals,
                sandbox_locals
            )

            result = await sandbox_locals["__user_fn__"]()

            return {
                "mode": "code",
                "success": True,
                "output": result
            }

        except Exception as e:
            return {
                "mode": "code",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "code": code
            }

    # ===========================================================
    # LLM EXECUTION
    # ===========================================================
    async def execute_llm(self, prompt: str, context: str | None):
        """
        Executes an LLM_CALL step using official Gemini SDK.
        """

        if not prompt:
            return {
                "mode": "llm",
                "success": False,
                "error": "Missing LLM prompt"
            }

        full_prompt = prompt
        if context:
            full_prompt += "\n\n" + str(context)

        try:
            response = self.gemini.models.generate_content(
                model=self.model,
                contents=full_prompt
            )
            text = response.text or ""

            return {
                "mode": "llm",
                "success": True,
                "output": text
            }

        except ServerError as e:
            return {
                "mode": "llm",
                "success": False,
                "error": f"Gemini ServerError: {str(e)}",
                "traceback": traceback.format_exc()
            }

        except Exception as e:
            return {
                "mode": "llm",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
