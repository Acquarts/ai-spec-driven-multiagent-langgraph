"""Nodo route_spec_types — decide qué tipos de spec generar y los lanza en paralelo."""

from __future__ import annotations

from typing import Literal

from langgraph.types import Send

from src.config import UTILITY_MODEL, call_model, parse_json_response
from src.state import SpecState

SpecType = Literal["openapi", "gherkin", "agent"]

SYSTEM = """Decides qué specs formales generar a partir de un resumen estructurado de requisitos.

Reglas:
- Incluye siempre "gherkin" (los escenarios BDD aplican a cualquier sistema).
- Incluye "openapi" cuando el sistema expone endpoints HTTP, APIs REST, operaciones CRUD o servicios web.
- Incluye "agent" cuando el sistema implica un asistente de IA, chatbot, LLM, agente de automatización o modelo con herramientas.

Responde SOLO con un objeto JSON: {"spec_types": ["openapi", "gherkin", "agent"]}.
Incluye únicamente los tipos que apliquen. Nunca devuelvas lista vacía: gherkin siempre está presente.

IMPORTANTE: los identificadores ("openapi", "gherkin", "agent") deben mantenerse en inglés tal cual."""


async def route_spec_types(state: SpecState) -> dict:
    if state.structured_requirements is None:
        return {"spec_types": ["gherkin"]}

    response = await call_model(
        model=UTILITY_MODEL,
        system=SYSTEM,
        user=state.structured_requirements.model_dump_json(indent=2),
        max_tokens=256,
        node="route_spec_types",
    )
    payload = parse_json_response(response)
    spec_types: list[str] = payload.get("spec_types") or ["gherkin"]
    if "gherkin" not in spec_types:
        spec_types.append("gherkin")
    return {"spec_types": spec_types}


def route_after_router(state: SpecState) -> list[Send]:
    """Fan-out: un Send por cada tipo de spec. LangGraph los ejecuta en paralelo."""
    return [Send(f"generate_{spec_type}", state) for spec_type in state.spec_types]
