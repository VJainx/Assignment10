"""
ToolRuntime — executes structured tool calls through MultiMCP or any registry.
"""

from typing import Any, Dict
from execution.execution_result import ExecutionResult


class ToolRuntime:

    def __init__(self, multi_mcp):
        self.multi_mcp = multi_mcp

    async def execute(self, tool_name: str, tool_args: Dict[str, Any]) -> ExecutionResult:
        try:
            result = await self.multi_mcp.execute(tool_name, tool_args)
            return ExecutionResult(success=True, data=result, output_type="tool")
        except Exception as e:
            return ExecutionResult(success=False, error=str(e), output_type="tool")
