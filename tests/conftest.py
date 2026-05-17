"""Fixtures comunes: mock del cliente Anthropic + helpers de estado."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Fija una API key fake ANTES de importar src.config (lo importa get_client).
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-fake-key-for-unit-tests-only"


def _hacer_response(text: str, input_tokens: int = 100, output_tokens: int = 200):
    """Construye un objeto que imita la respuesta de Anthropic.messages.create."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    response.stop_reason = "end_turn"
    return response


@pytest.fixture
def cliente_mock(monkeypatch):
    """Reemplaza el cliente Anthropic compartido por un mock.

    Uso: cliente_mock.messages.create.return_value = _hacer_response("...").
    """
    from src import config

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock()

    # get_client está cacheado con lru_cache — hay que limpiar el cache
    # para que devuelva nuestro mock en lugar del cliente real.
    config.get_client.cache_clear()
    monkeypatch.setattr(config, "get_client", lambda: mock_client)

    return mock_client


@pytest.fixture
def hacer_response():
    """Expone el constructor de responses como fixture."""
    return _hacer_response
