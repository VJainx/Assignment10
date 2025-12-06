"""
PythonRuntime — executes Python safely through your existing sandbox.
"""

from typing import Any
from execution.execution_result import ExecutionResult
from action.executor import run_user_code  # your existing safe executor


class PythonRuntime:

    def __init__(self, multi_mcp):
        self.multi_mcp = multi_mcp

    async def execute(self, code: str) -> ExecutionResult:
        try:
            result = await run_user_code(code, self.multi_mcp)
            return ExecutionResult(success=True, data=result, output_type="python")
        except Exception as e:
            return ExecutionResult(success=False, error=str(e), output_type="python")
