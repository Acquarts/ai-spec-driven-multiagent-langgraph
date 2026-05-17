"""Tests del módulo config: parsing JSON, strip de fences, validación de API key."""

from __future__ import annotations

import json

import pytest

from src.config import parse_json_response, strip_code_fences


class TestStripCodeFences:
    def test_sin_fences_devuelve_igual(self):
        assert strip_code_fences("hola mundo") == "hola mundo"

    def test_fence_json(self):
        text = "```json\n{\"a\": 1}\n```"
        assert strip_code_fences(text) == '{"a": 1}'

    def test_fence_yaml(self):
        text = "```yaml\nopenapi: 3.1.0\n```"
        assert strip_code_fences(text) == "openapi: 3.1.0"

    def test_fence_sin_lenguaje(self):
        text = "```\ncontenido\n```"
        assert strip_code_fences(text) == "contenido"


class TestParseJsonResponse:
    def test_json_limpio(self):
        assert parse_json_response('{"a": 1}') == {"a": 1}

    def test_json_con_fence(self):
        assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_con_prosa_antes(self):
        text = 'Aquí tienes la respuesta:\n{"a": 1}'
        assert parse_json_response(text) == {"a": 1}

    def test_json_con_prosa_despues(self):
        # raw_decode debe parsear el objeto e ignorar lo posterior.
        text = '{"a": 1}\nEspero que te sirva!'
        assert parse_json_response(text) == {"a": 1}

    def test_array(self):
        assert parse_json_response("[1, 2, 3]") == [1, 2, 3]

    def test_sin_json_lanza(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("solo texto sin json")
