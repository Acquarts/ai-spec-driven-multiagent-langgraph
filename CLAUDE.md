# Spec-Driven Development Agent — Project Plan

## Project Overview

Build a multi-agent system using **LangGraph** that takes natural language requirements as input and automatically generates formal specs of multiple types in parallel. The agent outputs production-ready spec artifacts: OpenAPI YAML, Gherkin feature files, and Agent specs (system prompt + tool definitions).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (`StateGraph`, `Send` API) |
| LLM | Anthropic Claude API (Haiku 3.5 + Sonnet 4) |
| State validation | Pydantic v2 |
| OpenAPI serialization | PyYAML |
| Python version | 3.11+ |
| Dependency management | `uv` or `pip` with `requirements.txt` |

---

## Project Structure

```
spec-agent/
├── CLAUDE.md                  # This file
├── requirements.txt
├── .env.example
├── main.py                    # CLI entrypoint
├── src/
│   ├── __init__.py
│   ├── state.py               # SpecState Pydantic model
│   ├── graph.py               # LangGraph StateGraph definition
│   └── nodes/
│       ├── __init__.py
│       ├── analyzer.py        # analyze_requirements node
│       ├── router.py          # route_spec_types node
│       ├── openapi.py         # generate_openapi node
│       ├── gherkin.py         # generate_gherkin node
│       ├── agent_spec.py      # generate_agent_spec node
│       ├── validator.py       # validate_specs node
│       └── consolidator.py    # consolidate node
└── output/                    # Generated specs (gitignored)
    └── .gitkeep
```

---

## Architecture

### Flow Diagram

```
User Input (natural language requirements)
    │
    ▼
[analyze_requirements]     → Extracts: entities, actions, constraints, domain
    │
    ▼
[route_spec_types]         → Decides which spec types to generate
    │
    ├─── Send("generate_openapi")
    ├─── Send("generate_gherkin")
    └─── Send("generate_agent_spec")
              │ (parallel via Send API)
              ▼
         [validate_specs]  → Validates syntax + completeness per spec type
              │
              ▼
         [consolidate]     → Generates unified README + output folder
              │
              ▼
         OUTPUT: /output/<timestamp>/
           ├── openapi.yaml
           ├── features/
           │   └── *.feature
           ├── agent/
           │   ├── system_prompt.md
           │   └── tools.json
           └── README.md
```

---

## State Definition (`src/state.py`)

```python
from typing import Annotated, Any
from pydantic import BaseModel, Field
import operator

class StructuredRequirements(BaseModel):
    domain: str                        # e.g. "e-commerce", "healthcare"
    entities: list[str]                # e.g. ["User", "Order", "Product"]
    actions: list[str]                 # e.g. ["create order", "list products"]
    constraints: list[str]             # e.g. ["auth required", "paginated"]
    integrations: list[str]            # e.g. ["payment gateway", "email service"]
    raw_summary: str                   # Human-readable summary of requirements

class ValidationResult(BaseModel):
    spec_type: str
    is_valid: bool
    issues: list[str]
    suggestions: list[str]

class SpecState(BaseModel):
    # Input
    raw_requirements: str

    # Processed
    structured_requirements: StructuredRequirements | None = None
    spec_types: list[str] = Field(default_factory=list)  # ["openapi", "gherkin", "agent"]

    # Generated specs (populated in parallel)
    generated_specs: Annotated[dict[str, str], operator.or_] = Field(default_factory=dict)

    # Validation
    validation_results: Annotated[list[ValidationResult], operator.add] = Field(default_factory=list)

    # Output
    output_path: str | None = None
    final_summary: str | None = None
```

---

## Node Specifications

### 1. `analyze_requirements` (`src/nodes/analyzer.py`)

**Model:** `claude-sonnet-4-20250514`
**Purpose:** Parse raw text into structured requirements.

**Prompt behavior:**
- Respond ONLY with valid JSON matching `StructuredRequirements` schema.
- Extract domain, entities (nouns), actions (verbs), technical constraints, and external integrations.
- If requirements are ambiguous, make reasonable assumptions and note them in `raw_summary`.

**Output:** Populates `state.structured_requirements`.

---

### 2. `route_spec_types` (`src/nodes/router.py`)

**Model:** `claude-haiku-4-5-20251001`
**Purpose:** Decide which spec types to generate based on the structured requirements.

**Logic:**
- Always generate `gherkin` (BDD applies to any system).
- Generate `openapi` if there are HTTP endpoints, REST APIs, or data CRUD operations.
- Generate `agent` if there are AI assistant, chatbot, automation, or LLM-related requirements.

**Output:** Populates `state.spec_types` as a list, e.g. `["openapi", "gherkin", "agent"]`.

**Routing:** Uses LangGraph `Send` API to dispatch parallel generation nodes based on `spec_types`.

```python
def route_after_router(state: SpecState) -> list[Send]:
    return [Send(f"generate_{spec_type}", state) for spec_type in state.spec_types]
```

---

### 3. `generate_openapi` (`src/nodes/openapi.py`)

**Model:** `claude-sonnet-4-20250514`
**Purpose:** Generate a complete OpenAPI 3.1.0 spec in YAML format.

**Prompt behavior:**
- Respond ONLY with valid YAML (no markdown fences, no preamble).
- Include: `info`, `servers`, `paths`, `components/schemas`, `components/securitySchemes`.
- Use RESTful conventions. Infer HTTP methods from actions (create→POST, list→GET, etc.).
- Add meaningful descriptions to all fields.
- Use `Bearer` auth if authentication is mentioned in constraints.

**Output:** `state.generated_specs["openapi"]` = YAML string.

---

### 4. `generate_gherkin` (`src/nodes/gherkin.py`)

**Model:** `claude-sonnet-4-20250514`
**Purpose:** Generate Gherkin `.feature` files for BDD testing.

**Prompt behavior:**
- Generate one feature file per entity or major action group.
- Each feature must have: `Feature`, `Background` (if applicable), and at least 3 `Scenario` blocks.
- Use `Given / When / Then / And` structure strictly.
- Cover happy paths AND edge cases (invalid input, not found, unauthorized).
- Output format: a JSON object where keys are filenames (e.g. `"orders.feature"`) and values are the Gherkin content string.

**Output:** `state.generated_specs["gherkin"]` = JSON string mapping filename → content.

---

### 5. `generate_agent_spec` (`src/nodes/agent_spec.py`)

**Model:** `claude-sonnet-4-20250514`
**Purpose:** Generate a Claude agent specification (system prompt + tool definitions).

**Prompt behavior:**
- Generate a `system_prompt.md` with: role, capabilities, constraints, tone, and output format instructions.
- Generate a `tools.json` following Anthropic tool use schema:
  ```json
  [
    {
      "name": "tool_name",
      "description": "...",
      "input_schema": {
        "type": "object",
        "properties": { ... },
        "required": [...]
      }
    }
  ]
  ```
- Output format: JSON object with keys `"system_prompt"` and `"tools"`.

**Output:** `state.generated_specs["agent"]` = JSON string with both artifacts.

---

### 6. `validate_specs` (`src/nodes/validator.py`)

**Model:** `claude-haiku-4-5-20251001`
**Purpose:** Validate each generated spec for syntax correctness and completeness.

**Validation checks per type:**

| Spec Type | Checks |
|---|---|
| `openapi` | Valid YAML, has `paths`, has `components/schemas`, all `$ref` resolvable |
| `gherkin` | Valid Gherkin syntax, has `Feature` + `Scenario`, uses Given/When/Then |
| `agent` | Valid JSON, `tools` array has `name`/`description`/`input_schema`, system prompt non-empty |

**Output:** Appends `ValidationResult` objects to `state.validation_results`.

---

### 7. `consolidate` (`src/nodes/consolidator.py`)

**Model:** `claude-haiku-4-5-20251001`
**Purpose:** Write all generated specs to disk and generate a unified `README.md`.

**Behavior:**
- Create output folder: `output/<ISO_timestamp>/`
- Write `openapi.yaml` if present.
- Write each Gherkin file parsed from the JSON map into `features/`.
- Parse agent JSON and write `agent/system_prompt.md` and `agent/tools.json`.
- Generate a `README.md` summarizing: domain, entities, spec types generated, validation results, and file index.

**Output:** Populates `state.output_path` and `state.final_summary`.

---

## Graph Definition (`src/graph.py`)

```python
from langgraph.graph import StateGraph, END
from langgraph.types import Send

def build_graph() -> StateGraph:
    graph = StateGraph(SpecState)

    graph.add_node("analyze_requirements", analyze_requirements)
    graph.add_node("route_spec_types", route_spec_types)
    graph.add_node("generate_openapi", generate_openapi)
    graph.add_node("generate_gherkin", generate_gherkin)
    graph.add_node("generate_agent_spec", generate_agent_spec)
    graph.add_node("validate_specs", validate_specs)
    graph.add_node("consolidate", consolidate)

    graph.set_entry_point("analyze_requirements")
    graph.add_edge("analyze_requirements", "route_spec_types")
    graph.add_conditional_edges("route_spec_types", route_after_router)
    graph.add_edge("generate_openapi", "validate_specs")
    graph.add_edge("generate_gherkin", "validate_specs")
    graph.add_edge("generate_agent_spec", "validate_specs")
    graph.add_edge("validate_specs", "consolidate")
    graph.add_edge("consolidate", END)

    return graph.compile()
```

---

## CLI Entrypoint (`main.py`)

```python
import asyncio
import argparse
from src.graph import build_graph
from src.state import SpecState

async def main():
    parser = argparse.ArgumentParser(description="Spec-Driven Development Agent")
    parser.add_argument("--requirements", "-r", type=str, help="Requirements as text")
    parser.add_argument("--file", "-f", type=str, help="Path to requirements .txt file")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            requirements = f.read()
    elif args.requirements:
        requirements = args.requirements
    else:
        requirements = input("Enter your requirements: ")

    graph = build_graph()
    initial_state = SpecState(raw_requirements=requirements)

    result = await graph.ainvoke(initial_state)

    print(f"\n✅ Specs generated at: {result['output_path']}")
    print(f"\n{result['final_summary']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Requirements (`requirements.txt`)

```
anthropic>=0.40.0
langgraph>=0.2.0
langchain-anthropic>=0.2.0
pydantic>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

---

## Environment Variables (`.env`)

```env
ANTHROPIC_API_KEY=your_key_here
```

---

## Implementation Order

Implement nodes in this exact order, testing each before proceeding:

1. `src/state.py` — SpecState + supporting models
2. `src/nodes/analyzer.py` — analyze_requirements
3. `src/nodes/router.py` — route_spec_types + Send routing function
4. `src/nodes/openapi.py` — generate_openapi
5. `src/nodes/gherkin.py` — generate_gherkin
6. `src/nodes/agent_spec.py` — generate_agent_spec
7. `src/nodes/validator.py` — validate_specs
8. `src/nodes/consolidator.py` — consolidate (file writing + README)
9. `src/graph.py` — assemble full StateGraph
10. `main.py` — CLI entrypoint

---

## Example Usage

```bash
# From requirements string
python main.py -r "Build a REST API for a task management app. Users can create, list, update and delete tasks. Tasks have a title, description, due date, and status. Auth is required via JWT."

# From requirements file
python main.py -f requirements.txt
```

---

## Notes for Implementation

- All LLM calls must use `async`/`await`.
- Wrap all LLM calls in try/except with retry logic (exponential backoff, max 3 retries) for `RateLimitError`.
- When generating YAML or JSON from LLM responses, strip markdown fences (` ```yaml `, ` ```json `) before parsing.
- Use `model_dump()` for Pydantic serialization when passing state to LLM prompts.
- The `generated_specs` and `validation_results` fields use LangGraph reducers (`operator.or_` and `operator.add`) to safely merge parallel node outputs.
- All file writes in `consolidate` should use `pathlib.Path` and `mkdir(parents=True, exist_ok=True)`.
