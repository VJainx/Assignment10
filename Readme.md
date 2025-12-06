# Graph-Native Agent Architecture

A Perception → Planning → Execution system with dynamic mid-session replanning

## 🚀 Overview

This project implements an advanced agentic reasoning system that replaces the classical linear pipeline with a fully graph-native architecture. By modeling reasoning as a PlanGraph (DAG), the agent can:

- Preserve progress across execution steps
- Recover from failures without restarting
- Add new branches dynamically
- Replan mid-session using structured perception signals
- Maintain deterministic and explainable reasoning paths

The system is modular and consists of:

**Perception → Planning → Execution → Evaluation → Replan (if needed)**

Each step produces structured information that feeds the next stage, enabling adaptive behavior and robust error handling.

## ✨ Key Features

### 1. PlanGraph (DAG-based Planning)

Each action becomes a node containing:

- Step type (TOOL, CODE, LLM_CALL, ASK_USER, CONCLUDE)
- Dependencies (parents)
- Runtime metadata (status, attempts, outputs)

The graph controls execution order:

- Only nodes whose parents are completed become runnable.

This allows partial execution, incremental building, and selective replanning.

### 2. ERORLL Perception Model

Perception no longer produces unstructured text.
Instead, every perception call returns a structured PerceptionSnapshot, containing:

- entities
- intent
- constraints
- missing_parameters
- original_goal_achieved
- local_goal_achieved
- reasoning / local_reasoning
- last_tooluse_summary
- solution_summary
- confidence

This snapshot is used by the Decision Module and Evaluation Engine to infer what should happen next.

### 3. Decision Module (Planning)

The decision module produces a pure JSON plan, always of the form:

```json
{
  "plan_text": [...],
  "plan_graph": {
    "nodes": [ ... ]
  }
}
```

It supports two modes:

#### initial planning
- Produce minimal plan (1–3 steps)
- No CONCLUDE unless perception already knows the answer
- Use the tool → extraction → optional formatting pattern

#### mid-session replanning
- Patch ONLY the failed branch
- Add new nodes instead of replacing old ones
- Never rewrite or delete existing graph nodes
- Introduce fallbacks (e.g., DuckDuckGo → ASK_USER)
- Add CONCLUDE only when a concrete value is available

### 4. Execution Engine

Executes each step depending on type:

| Step Type | Behavior |
|-----------|----------|
| TOOL      | Calls an MCP tool |
| CODE      | Executes Python code |
| LLM_CALL  | Sends prompt + context to the LLM |
| ASK_USER  | Requests user input |
| CONCLUDE  | Produces the final answer |

Execution results are passed to perception to determine the next action.

### 5. Evaluation Engine

Interprets:
- execution output
- perception snapshot
- step metadata

Produces:

```json
{
  "global_success": bool,
  "needs_replan": bool,
  "final_answer": Optional[str],
  "reasoning": str
}
```

Examples:
- Tool failure → needs_replan = True
- Extraction succeeded → planner may add CONCLUDE next
- User answered → final answer is ready

### 6. Dynamic Mid-Session Replanning

The agent no longer restarts or discards earlier progress.

When a step fails:

**Perception → Evaluate → Replan → Insert new nodes → Continue**

Only the problematic part of the graph is replaced.
All other successful nodes remain untouched.

This enables:
- fallback tools
- additional extraction attempts
- ask-user when tools fail
- branching logic
- late introduction of CONCLUDE steps

## 📐 Data Flow Diagram

```
┌─────────────────┐
│   User Query     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│   Perception     │  (ERORLL snapshot)
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│   Decision       │  (PlanGraph DAG)
└─────────┬───────┘
          │
          ▼
┌────────────────────────┐
│ Execution Engine        │
│  - TOOL / LLM / CODE    │
└─────────┬──────────────┘
          │
          ▼
┌─────────────────┐
│  Perception      │  (step_result snapshot)
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  Evaluation      │  → success? → DONE
│                  │  → failure? → REPLAN
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│    Replan       │  (patch DAG)
└─────────┬───────┘
          │
          └──→ Back to Execution
```

## 🧠 Why This Architecture?

### Problems with the old linear architecture:

- Repeated the same steps on every cycle
- No persistence or memory of successful execution
- Planner could not inspect or modify existing structure
- Error recovery required full restarts
- Perception was unstructured → brittle decision signals

### Advantages of the new system:

- Graph prevents redoing work
- Perception gives high-quality semantic signals
- Planner becomes a true dynamic reasoning engine
- Robust fallback support (DuckDuckGo → Ask User → Conclude)
- No hallucinating of runtime variables
- Strict JSON guarantees reproducibility and safety

## 🧩 Repository Structure

```
/agent
  agent_loop.py         → main orchestrator
  perception_snapshot.py → ERORLL schema
  step.py               → Step models & enums

/decision
  decision.py           → planner (initial + mid-session)

/perception
  perception.py         → perception LLM interface

/planning
  plan_graph.py         → DAG implementation

/execution
  execution_engine.py   → tool/code/LLM execution

/evaluation
  evaluation_engine.py  → step evaluation logic

/memory
  memory_search.py      → optional retrieval module
```

## 🛠️ How to Run

```python
loop = AgentLoop(
    perception_prompt_path="prompts/perception.txt",
    decision_prompt_path="prompts/decision.txt",
    multi_mcp=mcp_client
)

session = await loop.run("What is the Sensex today?")
print(session.final_answer)
```

## 📌 Important Design Constraints

### 1. Planner output must be pure JSON

No markdown, no comments, no placeholders.

### 2. Planner cannot use runtime variable names

NO:
```
{{step1.value}}
{{tool_output}}
{{node_0.result}}
```

### 3. LLM extraction must follow strict format:
```json
{ "value": ... }
```

### 4. Tool names must be real (listed in tool_list)

## 🧪 Testing

Each module can be tested in isolation:

- Perception prompt debugging
- Decision module dry-run tests
- DAG traversal validation
- Execution engine error handling
- Replan patch insertion tests

## 🏁 Final Notes

This architecture is built for:

- High reliability
- Debuggability
- Extensibility
- Safety
- Reproducibility

It is suitable for:

- Search agents
- Reasoning agents
- Conversational assistants
- Automated research tools
- Multi-step problem solving systems