"""
LLMRuntime — unified LLM interface for non-planner, non-perception tasks.
"""

from execution.execution_result import ExecutionResult
from google import genai


class LLMRuntime:

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def execute(self, prompt: str, context: str = "") -> ExecutionResult:
        try:
            full_input = f"{prompt}\n\n{context}"
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_input
            )
            return ExecutionResult(
                success=True,
                data=response.text,
                output_type="llm"
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e), output_type="llm")
