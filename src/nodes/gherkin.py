"""Nodo generate_gherkin — produce un archivo .feature por entidad/grupo de acciones."""

from __future__ import annotations

import json

from src.config import GENERATION_MODEL, call_model, parse_json_response
from src.state import GenerationError, SpecState

SYSTEM = """Eres un QA senior que redacta especificaciones BDD en Gherkin.

Genera archivos .feature a partir de los requisitos siguientes.

REGLAS DE SALIDA ESTRICTAS:
- Responde SOLO con un único objeto JSON. Sin prosa, sin fences markdown.
- Las claves son nombres de archivo terminados en `.feature` (snake_case, p. ej. "pedidos.feature").
- Los valores son el contenido Gherkin completo como una sola cadena (usa \\n para los saltos de línea).

IDIOMA Y SINTAXIS GHERKIN EN ESPAÑOL:
- TODOS los archivos deben empezar con la directiva de idioma: `# language: es`
- Usa estrictamente las palabras clave oficiales de Gherkin en español:
  · `Característica:`   (en vez de Feature:)
  · `Antecedentes:`     (en vez de Background:)
  · `Escenario:`        (en vez de Scenario:)
  · `Esquema del escenario:` (en vez de Scenario Outline:)
  · `Dado` / `Cuando` / `Entonces` / `Y` / `Pero`   (en vez de Given/When/Then/And/But)
  · `Ejemplos:` para tablas de Scenario Outline

REGLAS DE CONTENIDO:
- Genera un archivo por entidad o por grupo principal de acciones.
- Cada `Característica:` debe tener una descripción de una línea debajo.
- Incluye `Antecedentes:` cuando haya configuración compartida (p. ej. usuario autenticado).
- Cada Característica debe contener AL MENOS 3 bloques `Escenario:`.
- Cubre: camino feliz, caso de validación/borde (entrada inválida), y caso de autorización o no encontrado.
- Sin texto libre fuera de los pasos.
- Usa valores de ejemplo concretos y realistas — no marcadores como `<valor>`.

Ejemplo del formato esperado:
{
  "pedidos.feature": "# language: es\\nCaracterística: Gestión de pedidos\\n  ...",
  "usuarios.feature": "# language: es\\nCaracterística: Gestión de usuarios\\n  ..."
}"""


async def generate_gherkin(state: SpecState) -> dict:
    if state.structured_requirements is None:
        return {
            "generation_errors": [
                GenerationError(
                    spec_type="gherkin",
                    message="structured_requirements no disponible antes de generar gherkin",
                )
            ]
        }

    user_prompt = (
        "Requisitos estructurados (JSON):\n"
        f"{state.structured_requirements.model_dump_json(indent=2)}\n\n"
        "Genera ahora el objeto JSON con los archivos .feature."
    )

    try:
        response = await call_model(
            model=GENERATION_MODEL,
            system=SYSTEM,
            user=user_prompt,
            max_tokens=12288,
            node="generate_gherkin",
        )
        payload = parse_json_response(response)
        if not isinstance(payload, dict) or not payload:
            raise ValueError("la respuesta gherkin debe ser un objeto JSON no vacío")
        return {"generated_specs": {"gherkin": json.dumps(payload)}}
    except Exception as exc:
        return {
            "generation_errors": [
                GenerationError(spec_type="gherkin", message=str(exc))
            ]
        }
