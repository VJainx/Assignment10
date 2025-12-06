from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ExecutionResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    output_type: str = "generic"
