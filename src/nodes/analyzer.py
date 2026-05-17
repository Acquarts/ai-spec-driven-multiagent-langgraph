"""Nodo analyze_requirements — convierte texto libre en StructuredRequirements."""

from __future__ import annotations

from src.config import GENERATION_MODEL, call_model, parse_json_response
from src.state import SpecState, StructuredRequirements

SYSTEM = """Eres un analista que extrae requisitos de software estructurados a partir de lenguaje natural.

Responde SOLO con un único objeto JSON (sin prosa, sin fences markdown) que cumpla este esquema:

{
  "domain": "nombre corto del dominio, p. ej. e-commerce, salud, devtools",
  "entities": ["sustantivos que el sistema gestiona, p. ej. Usuario, Pedido"],
  "actions": ["verbos/operaciones, p. ej. crear pedido, listar productos"],
  "constraints": ["reglas técnicas o de negocio, p. ej. autenticación requerida, paginado"],
  "integrations": ["sistemas externos, p. ej. stripe, sendgrid"],
  "raw_summary": "resumen humano de 1 a 3 frases, indicando cualquier supuesto que hayas hecho"
}

Reglas:
- Todo el contenido textual (entities, actions, constraints, integrations, raw_summary) debe estar EN ESPAÑOL.
- Si los requisitos son vagos, asume razonablemente y anótalo en raw_summary.
- Nunca devuelvas null. Usa listas vacías cuando algo no aplique."""


async def analyze_requirements(state: SpecState) -> dict:
    response = await call_model(
        model=GENERATION_MODEL,
        system=SYSTEM,
        user=state.raw_requirements,
        max_tokens=2048,
        node="analyze_requirements",
    )
    payload = parse_json_response(response)
    structured = StructuredRequirements(**payload)
    return {"structured_requirements": structured}
