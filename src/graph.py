"""Ensamblaje del LangGraph: analizar → enrutar → (fan-out generadores) → validar → consolidar."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.nodes import (
    analyze_requirements,
    consolidate,
    generate_agent_spec,
    generate_gherkin,
    generate_openapi,
    route_after_router,
    route_spec_types,
    validate_specs,
)
from src.state import SpecState


def _build() -> StateGraph:
    graph = StateGraph(SpecState)

    graph.add_node("analyze_requirements", analyze_requirements)
    graph.add_node("route_spec_types", route_spec_types)
    graph.add_node("generate_openapi", generate_openapi)
    graph.add_node("generate_gherkin", generate_gherkin)
    graph.add_node("generate_agent", generate_agent_spec)
    graph.add_node("validate_specs", validate_specs)
    graph.add_node("consolidate", consolidate)

    graph.set_entry_point("analyze_requirements")
    graph.add_edge("analyze_requirements", "route_spec_types")
    graph.add_conditional_edges(
        "route_spec_types",
        route_after_router,
        ["generate_openapi", "generate_gherkin", "generate_agent"],
    )
    graph.add_edge("generate_openapi", "validate_specs")
    graph.add_edge("generate_gherkin", "validate_specs")
    graph.add_edge("generate_agent", "validate_specs")
    graph.add_edge("validate_specs", "consolidate")
    graph.add_edge("consolidate", END)

    return graph.compile()


@lru_cache(maxsize=1)
def build_graph():
    """Devuelve el grafo compilado (cacheado — la compilación es pura)."""
    return _build()
