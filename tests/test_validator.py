"""Tests del nodo validator: deterministas, no llaman al LLM."""

from __future__ import annotations

import asyncio
import json

from src.nodes.validator import (
    _validate_agent,
    _validate_gherkin,
    _validate_openapi,
    validate_specs,
)
from src.state import GenerationError, SpecState


# ---- OpenAPI ----------------------------------------------------------------

OPENAPI_VALIDO = """
openapi: 3.1.0
info:
  title: API de prueba
  version: 1.0.0
paths:
  /items:
    get:
      operationId: listItems
      responses:
        '200':
          description: ok
components:
  schemas:
    Item:
      type: object
      properties:
        id:
          type: string
      required:
        - id
"""


def test_openapi_valido_pasa():
    result = _validate_openapi(OPENAPI_VALIDO)
    assert result.is_valid
    assert result.issues == []


def test_openapi_sin_paths_falla():
    yaml_text = "openapi: 3.1.0\ninfo:\n  title: x\n  version: 1.0.0\n"
    result = _validate_openapi(yaml_text)
    assert not result.is_valid


def test_openapi_yaml_corrupto_falla():
    result = _validate_openapi("openapi: 3.1.0\n  : bad indent\n[invalid")
    assert not result.is_valid
    assert any("YAML" in i or "OpenAPI" in i for i in result.issues)


# ---- OpenAPI: post-procesado defensivo de $ref ------------------------------

def test_fix_refs_corrige_ref_sin_dollar():
    from src.nodes.openapi import _fix_refs

    yaml_text = "schema:\n  ref: '#/components/schemas/Usuario'\n"
    fixed = _fix_refs(yaml_text)
    assert "$ref: '#/components/schemas/Usuario'" in fixed
    assert "  ref:" not in fixed


def test_fix_refs_corrige_undefinedref():
    from src.nodes.openapi import _fix_refs

    yaml_text = "schema:\n  undefinedref: '#/components/schemas/Pedido'\n"
    fixed = _fix_refs(yaml_text)
    assert "$ref: '#/components/schemas/Pedido'" in fixed
    assert "undefinedref" not in fixed


def test_fix_refs_no_toca_ref_correcto():
    from src.nodes.openapi import _fix_refs

    yaml_text = "schema:\n  $ref: '#/components/schemas/Usuario'\n"
    assert _fix_refs(yaml_text) == yaml_text


def test_fix_refs_no_toca_palabras_que_terminan_en_ref():
    from src.nodes.openapi import _fix_refs

    # 'preferred' contiene 'ref' pero no es un JSON ref, no se toca.
    yaml_text = "description: 'Color preferred: #/red'\n"
    fixed = _fix_refs(yaml_text)
    assert fixed == yaml_text


# ---- Gherkin ----------------------------------------------------------------

GHERKIN_ES = {
    "pedidos.feature": (
        "# language: es\n"
        "Característica: Gestión de pedidos\n"
        "  Escenario: Crear pedido\n"
        "    Dado un usuario autenticado\n"
        "    Cuando crea un pedido\n"
        "    Entonces el pedido se guarda\n"
    )
}


def test_gherkin_espanol_pasa():
    result = _validate_gherkin(json.dumps(GHERKIN_ES))
    assert result.is_valid, result.issues


def test_gherkin_ingles_tambien_pasa():
    files = {
        "orders.feature": (
            "Feature: Orders\n"
            "  Scenario: Create\n"
            "    Given an authenticated user\n"
            "    When they create an order\n"
            "    Then it is saved\n"
        )
    }
    result = _validate_gherkin(json.dumps(files))
    assert result.is_valid, result.issues


def test_gherkin_sin_pasos_falla():
    files = {
        "vacio.feature": "# language: es\nCaracterística: Vacío\n"
    }
    result = _validate_gherkin(json.dumps(files))
    assert not result.is_valid


def test_gherkin_json_invalido_falla():
    result = _validate_gherkin("no soy json")
    assert not result.is_valid


def test_gherkin_filename_malo_falla():
    files = {"sin_extension": "# language: es\nCaracterística: x\n..."}
    result = _validate_gherkin(json.dumps(files))
    assert not result.is_valid
    assert any(".feature" in i for i in result.issues)


# ---- Agent ------------------------------------------------------------------

AGENT_VALIDO = {
    "system_prompt": "# Rol\nEres un agente útil.",
    "tools": [
        {
            "name": "buscar",
            "description": "Busca cosas",
            "input_schema": {
                "type": "object",
                "properties": {"q": {"type": "string", "description": "consulta"}},
                "required": ["q"],
            },
        }
    ],
}


def test_agent_valido_pasa():
    result = _validate_agent(json.dumps(AGENT_VALIDO))
    assert result.is_valid, result.issues


def test_agent_sin_system_prompt_falla():
    payload = dict(AGENT_VALIDO, system_prompt="")
    result = _validate_agent(json.dumps(payload))
    assert not result.is_valid


def test_agent_sin_tools_falla():
    payload = dict(AGENT_VALIDO, tools=[])
    result = _validate_agent(json.dumps(payload))
    assert not result.is_valid


def test_agent_tool_sin_input_schema_falla():
    payload = dict(AGENT_VALIDO)
    payload["tools"] = [{"name": "x", "description": "y"}]
    result = _validate_agent(json.dumps(payload))
    assert not result.is_valid


# ---- Integración del nodo completo ------------------------------------------

def test_validate_specs_recoge_generation_errors():
    state = SpecState(
        raw_requirements="x",
        generated_specs={"openapi": OPENAPI_VALIDO},
        generation_errors=[
            GenerationError(spec_type="gherkin", message="el LLM tuvo un día malo")
        ],
    )
    result = asyncio.run(validate_specs(state))
    tipos = {r.spec_type: r for r in result["validation_results"]}
    assert tipos["openapi"].is_valid
    assert not tipos["gherkin"].is_valid
    assert "el LLM tuvo un día malo" in tipos["gherkin"].issues[0]
