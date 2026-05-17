"""Nodo generate_agent_spec — produce system prompt + tools.json para un agente Claude."""

from __future__ import annotations

import json

from src.config import GENERATION_MODEL, call_model, parse_json_response
from src.state import GenerationError, SpecState

SYSTEM = """Diseñas agentes Claude. Produce un system prompt y definiciones de herramientas a partir de los requisitos siguientes.

REGLAS DE SALIDA ESTRICTAS:
- Responde SOLO con un único objeto JSON. Sin prosa, sin fences markdown.
- El JSON debe ser ENTERAMENTE VÁLIDO: comillas cerradas, llaves balanceadas, comas correctas.
- Si el contenido se está alargando, recorta herramientas o acorta descripciones — un JSON corto y válido es infinitamente mejor que uno largo y truncado.
- Los saltos de línea dentro de strings DEBEN ir escapados como \\n.
- Estructura:
  {
    "system_prompt": "<system prompt completo en markdown como una sola cadena>",
    "tools": [
      {
        "name": "nombre_herramienta_en_snake_case",
        "description": "Qué hace la herramienta y cuándo usarla.",
        "input_schema": {
          "type": "object",
          "properties": { "parametro": {"type": "string", "description": "..."} },
          "required": ["parametro"]
        }
      }
    ]
  }

CONTENIDO DEL SYSTEM PROMPT:
- Secciones (como encabezados markdown): Rol, Capacidades, Restricciones, Tono, Formato de Salida.
- Sé específico sobre cómo el agente debe usar las herramientas listadas.

CONTENIDO DE LAS HERRAMIENTAS:
- Una herramienta por cada acción principal de los requisitos (p. ej. crear_pedido, listar_pedidos, obtener_pedido).
- Sigue estrictamente el esquema de tool use de Anthropic (JSON Schema para input_schema).
- Cada propiedad debe tener `type` y `description`.
- `required` debe listar cada propiedad realmente obligatoria.

IDIOMA:
- El system_prompt y todos los `description` deben estar EN ESPAÑOL.
- Los `name` de herramientas y los nombres de propiedades en snake_case (sin tildes, sin ñ — usa "n" en su lugar)."""


async def generate_agent_spec(state: SpecState) -> dict:
    if state.structured_requirements is None:
        return {
            "generation_errors": [
                GenerationError(
                    spec_type="agent",
                    message="structured_requirements no disponible antes de generar el agente",
                )
            ]
        }

    user_prompt = (
        "Requisitos estructurados (JSON):\n"
        f"{state.structured_requirements.model_dump_json(indent=2)}\n\n"
        "Genera ahora el objeto JSON del agente."
    )

    try:
        response = await call_model(
            model=GENERATION_MODEL,
            system=SYSTEM,
            user=user_prompt,
            max_tokens=12288,
            node="generate_agent",
        )
        payload = parse_json_response(response)
        if (
            not isinstance(payload, dict)
            or "system_prompt" not in payload
            or "tools" not in payload
        ):
            raise ValueError(
                "la respuesta del agente debe incluir 'system_prompt' y 'tools'"
            )
        return {"generated_specs": {"agent": json.dumps(payload)}}
    except Exception as exc:
        return {
            "generation_errors": [
                GenerationError(spec_type="agent", message=str(exc))
            ]
        }
