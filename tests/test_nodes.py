"""Tests de los nodos que llaman al LLM, usando cliente Anthropic mockeado."""

from __future__ import annotations

import asyncio
import json


# ---- analyzer ---------------------------------------------------------------

def test_analyzer_parsea_json_correcto(cliente_mock, hacer_response):
    from src.nodes.analyzer import analyze_requirements
    from src.state import SpecState

    payload = {
        "domain": "tareas",
        "entities": ["Tarea"],
        "actions": ["crear", "listar"],
        "constraints": [],
        "integrations": [],
        "raw_summary": "App de tareas básica.",
    }
    cliente_mock.messages.create.return_value = hacer_response(json.dumps(payload))

    state = SpecState(raw_requirements="quiero una app de tareas")
    result = asyncio.run(analyze_requirements(state))

    assert result["structured_requirements"].domain == "tareas"
    assert result["structured_requirements"].entities == ["Tarea"]


def test_analyzer_tolera_prosa_alrededor_del_json(cliente_mock, hacer_response):
    from src.nodes.analyzer import analyze_requirements
    from src.state import SpecState

    payload = {
        "domain": "test",
        "entities": [],
        "actions": [],
        "constraints": [],
        "integrations": [],
        "raw_summary": "x",
    }
    respuesta = f"Aquí tienes:\n{json.dumps(payload)}\nEspero que sirva!"
    cliente_mock.messages.create.return_value = hacer_response(respuesta)

    state = SpecState(raw_requirements="x")
    result = asyncio.run(analyze_requirements(state))
    assert result["structured_requirements"].domain == "test"


# ---- router -----------------------------------------------------------------

def test_router_siempre_incluye_gherkin(cliente_mock, hacer_response):
    from src.nodes.router import route_spec_types
    from src.state import SpecState, StructuredRequirements

    cliente_mock.messages.create.return_value = hacer_response(
        '{"spec_types": ["openapi"]}'
    )

    state = SpecState(
        raw_requirements="x",
        structured_requirements=StructuredRequirements(
            domain="x", entities=[], actions=[], constraints=[], integrations=[],
            raw_summary="x",
        ),
    )
    result = asyncio.run(route_spec_types(state))
    assert "gherkin" in result["spec_types"]
    assert "openapi" in result["spec_types"]


def test_router_sin_structured_requirements_devuelve_solo_gherkin():
    from src.nodes.router import route_spec_types
    from src.state import SpecState

    state = SpecState(raw_requirements="x")
    result = asyncio.run(route_spec_types(state))
    assert result["spec_types"] == ["gherkin"]


# ---- generadores: caminos de fallo ------------------------------------------

def test_openapi_sin_structured_requirements_registra_error():
    from src.nodes.openapi import generate_openapi
    from src.state import SpecState

    state = SpecState(raw_requirements="x")
    result = asyncio.run(generate_openapi(state))
    assert result["generation_errors"][0].spec_type == "openapi"


def test_gherkin_response_no_es_dict_registra_error(cliente_mock, hacer_response):
    from src.nodes.gherkin import generate_gherkin
    from src.state import SpecState, StructuredRequirements

    # El LLM devolvió un array en vez de un objeto.
    cliente_mock.messages.create.return_value = hacer_response('["malo"]')

    state = SpecState(
        raw_requirements="x",
        structured_requirements=StructuredRequirements(
            domain="x", entities=[], actions=[], constraints=[], integrations=[],
            raw_summary="x",
        ),
    )
    result = asyncio.run(generate_gherkin(state))
    assert "generation_errors" in result
    assert result["generation_errors"][0].spec_type == "gherkin"


def test_agent_response_sin_claves_obligatorias_registra_error(
    cliente_mock, hacer_response
):
    from src.nodes.agent_spec import generate_agent_spec
    from src.state import SpecState, StructuredRequirements

    cliente_mock.messages.create.return_value = hacer_response('{"tools": []}')

    state = SpecState(
        raw_requirements="x",
        structured_requirements=StructuredRequirements(
            domain="x", entities=[], actions=[], constraints=[], integrations=[],
            raw_summary="x",
        ),
    )
    result = asyncio.run(generate_agent_spec(state))
    assert "generation_errors" in result
    assert "system_prompt" in result["generation_errors"][0].message
