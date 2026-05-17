"""Nodo generate_openapi — produce un spec OpenAPI 3.1.0 en YAML."""

from __future__ import annotations

import re

from src.config import GENERATION_MODEL, call_model, strip_code_fences
from src.state import GenerationError, SpecState

# El LLM ocasionalmente escribe `ref:` o `undefinedref:` apuntando a un JSON
# Reference, cuando debería ser `$ref:`. Esto rompe la validación OpenAPI.
# Como no hay interpretación válida para esos casos (un `ref:` con valor
# `#/components/...` claramente es un typo del modelo), los corregimos.
_REF_FIX_RE = re.compile(r"(?<![\w$])(?:undefined)?ref(\s*:\s*['\"]?)#/")


def _fix_refs(yaml_text: str) -> str:
    """Reescribe 'ref:' y 'undefinedref:' como '$ref:' cuando apuntan a #/…"""
    return _REF_FIX_RE.sub(r"$ref\1#/", yaml_text)

SYSTEM = """Eres un diseñador experto de APIs.

Genera una especificación OpenAPI 3.1.0 completa y válida en YAML a partir de los requisitos siguientes.

REGLAS DE SALIDA ESTRICTAS:
- Responde SOLO con YAML válido. Sin prosa, sin fences markdown.
- La primera línea debe ser `openapi: 3.1.0`.

REGLAS DE CONTENIDO:
- Incluye `info` (title, version 1.0.0, description) y al menos una entrada en `servers`.
- Define `paths` para cada acción. Infiere los métodos HTTP a partir de los verbos:
  crear → POST, listar/obtener/leer → GET, actualizar → PUT/PATCH, eliminar → DELETE.
- Usa nombres de recursos RESTful (/pedidos, /pedidos/{id}).
- Cada operación debe tener: operationId, summary, tags, parameters (cuando aplique), requestBody (en operaciones de escritura) y responses para 200/201, 400, 401 (si hay auth), 404, 500.
- Define `components/schemas` para cada entidad, con propiedades tipadas realistas y listas `required`.
- Referencia los esquemas con `$ref: '#/components/schemas/Nombre'` — nunca dupliques inline.
- Si en las constraints aparece "autenticación requerida" o similar, declara `components/securitySchemes/BearerAuth` (type: http, scheme: bearer, bearerFormat: JWT) y aplícalo globalmente con `security` en la raíz.
- Añade `description` significativos a CADA campo y operación.

REGLA CRÍTICA SOBRE `schema` (causa el error más común):
- En OpenAPI 3.1, TODO valor `schema:` debe ser un OBJETO, nunca una cadena.
- ❌ MAL:  `schema: string`
- ✅ BIEN: `schema: { type: string }`  (o multilínea:  schema:\\n  type: string)
- Lo mismo aplica dentro de `parameters`, `requestBody.content.*.schema` y `responses.*.content.*.schema`.

REGLA CRÍTICA SOBRE `$ref` (segundo error más común):
- Siempre escribe `$ref` con el SÍMBOLO DÓLAR ($) por delante. NUNCA escribas `ref:` solo.
- ❌ MAL:  `ref: '#/components/schemas/Usuario'`
- ❌ MAL:  `undefinedref: '#/components/schemas/Usuario'`
- ✅ BIEN: `$ref: '#/components/schemas/Usuario'`
- Esto aplica en TODAS las referencias a schemas, parámetros, respuestas, etc.

Ejemplo mínimo de un parameter correcto:
  parameters:
    - name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
      description: Identificador del recurso

PRESUPUESTO DE TOKENS — LÉELO ANTES DE EMPEZAR:
- Tienes un máximo aproximado de 20.000 tokens de salida (~70 KB de YAML).
- Para sistemas con más de 8 entidades, GENERA SOLO LAS 6-8 ENTIDADES MÁS IMPORTANTES (las core del dominio).
- Para sistemas con más de 12 acciones, prioriza los 10-12 endpoints más relevantes.
- Está PROHIBIDO truncar a mitad. Un YAML cortado por la mitad es inservible.
- Es infinitamente mejor un spec con 6 schemas y 10 paths completo y válido,
  que uno con 15 schemas y 25 paths que se corta a mitad y rompe la sintaxis.
- Si dudas, RECORTA. Las entidades secundarias se pueden añadir después.

IDIOMA:
- Todo el texto humano (summary, description, tags) debe estar EN ESPAÑOL.
- Las claves de OpenAPI (openapi, info, paths, components, etc.), los nombres de operationId y los identificadores de schema se mantienen en inglés/PascalCase estándar.
- Los nombres de rutas pueden estar en español (p. ej. /pedidos, /usuarios)."""


async def generate_openapi(state: SpecState) -> dict:
    if state.structured_requirements is None:
        return {
            "generation_errors": [
                GenerationError(
                    spec_type="openapi",
                    message="structured_requirements no disponible antes de generar openapi",
                )
            ]
        }

    user_prompt = (
        "Requisitos estructurados (JSON):\n"
        f"{state.structured_requirements.model_dump_json(indent=2)}\n\n"
        "Genera ahora el YAML OpenAPI 3.1.0 completo."
    )

    try:
        response = await call_model(
            model=GENERATION_MODEL,
            system=SYSTEM,
            user=user_prompt,
            max_tokens=20480,
            node="generate_openapi",
        )
        yaml_text = strip_code_fences(response)
        yaml_text = _fix_refs(yaml_text)
        return {"generated_specs": {"openapi": yaml_text}}
    except Exception as exc:
        return {
            "generation_errors": [
                GenerationError(spec_type="openapi", message=str(exc))
            ]
        }
