"""Nodo validate_specs — validación determinista usando parsers reales."""

from __future__ import annotations

import json

import yaml
from openapi_spec_validator import validate as validate_openapi_spec
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

from src.state import GenerationError, SpecState, ValidationResult


def _validate_openapi(content: str) -> ValidationResult:
    issues: list[str] = []
    suggestions: list[str] = []
    parsed: dict | None = None

    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return ValidationResult(
            spec_type="openapi",
            is_valid=False,
            issues=[f"error al parsear YAML: {exc}"],
        )

    if not isinstance(parsed, dict):
        return ValidationResult(
            spec_type="openapi",
            is_valid=False,
            issues=["el documento OpenAPI debe ser un mapa en la raíz"],
        )

    if "paths" not in parsed:
        issues.append("falta la sección 'paths'")
    if "components" not in parsed or "schemas" not in (parsed.get("components") or {}):
        issues.append("falta 'components/schemas'")
        suggestions.append("define esquemas reutilizables bajo components.schemas")

    try:
        validate_openapi_spec(parsed)
    except OpenAPIValidationError as exc:
        issues.append(f"validación del esquema OpenAPI fallida: {exc.message}")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"error del validador OpenAPI: {exc}")

    return ValidationResult(
        spec_type="openapi",
        is_valid=not issues,
        issues=issues,
        suggestions=suggestions,
    )


# Palabras clave Gherkin: aceptamos español (preferido) e inglés (compatibilidad).
_FEATURE_KEYWORDS = ("Característica:", "Caracteristica:", "Feature:")
_SCENARIO_KEYWORDS = (
    "Escenario:",
    "Esquema del escenario:",
    "Scenario:",
    "Scenario Outline:",
)
# Sets de "al menos un Dado/Cuando/Entonces" (ES) o "Given/When/Then" (EN).
_STEP_KEYWORD_SETS = (
    ("Dado", "Cuando", "Entonces"),
    ("Given", "When", "Then"),
)


def _contains_any(text: str, options: tuple[str, ...]) -> bool:
    return any(opt in text for opt in options)


def _has_complete_step_set(text: str) -> bool:
    """Verdadero si el archivo contiene un conjunto completo de pasos (ES o EN)."""
    return any(all(k in text for k in keywords) for keywords in _STEP_KEYWORD_SETS)


def _validate_gherkin(content: str) -> ValidationResult:
    issues: list[str] = []
    suggestions: list[str] = []

    try:
        files = json.loads(content)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            spec_type="gherkin",
            is_valid=False,
            issues=[f"el payload gherkin no es JSON válido: {exc}"],
        )

    if not isinstance(files, dict) or not files:
        return ValidationResult(
            spec_type="gherkin",
            is_valid=False,
            issues=["se esperaba un objeto JSON no vacío con forma {nombre_archivo: contenido}"],
        )

    # Importación perezosa: el validador sigue siendo importable si la librería falta.
    try:
        from gherkin.parser import Parser as GherkinParser  # type: ignore

        parser_cls = GherkinParser
    except Exception:  # noqa: BLE001
        parser_cls = None
        suggestions.append(
            "instala 'gherkin-official' para validación de sintaxis completa; "
            "se está aplicando solo una comprobación estructural"
        )

    for filename, body in files.items():
        if not filename.endswith(".feature"):
            issues.append(f"{filename}: el nombre del archivo debe terminar en .feature")

        if not isinstance(body, str):
            issues.append(f"{filename}: el contenido debe ser una cadena")
            continue

        # Recomendación: archivos en español deberían declarar el idioma.
        first_line = body.lstrip().splitlines()[0] if body.strip() else ""
        has_lang_directive = first_line.startswith("# language:")
        if not has_lang_directive and _contains_any(body, ("Característica:", "Caracteristica:")):
            suggestions.append(
                f"{filename}: añade '# language: es' como primera línea para "
                "que gherkin-official reconozca las palabras clave en español"
            )

        if not _contains_any(body, _FEATURE_KEYWORDS):
            issues.append(f"{filename}: falta el encabezado 'Característica:' (o 'Feature:')")
            continue
        if not _contains_any(body, _SCENARIO_KEYWORDS):
            issues.append(f"{filename}: no se encontraron bloques 'Escenario:' (o 'Scenario:')")
        if not _has_complete_step_set(body):
            issues.append(
                f"{filename}: faltan pasos completos — se esperaban 'Dado/Cuando/Entonces' "
                "(o 'Given/When/Then' en inglés)"
            )

        if parser_cls is not None:
            try:
                parser_cls().parse(body)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"{filename}: error al parsear gherkin: {exc}")

    return ValidationResult(
        spec_type="gherkin",
        is_valid=not issues,
        issues=issues,
        suggestions=suggestions,
    )


def _validate_agent(content: str) -> ValidationResult:
    issues: list[str] = []
    suggestions: list[str] = []

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            spec_type="agent",
            is_valid=False,
            issues=[f"el payload del agente no es JSON válido: {exc}"],
        )

    if not isinstance(payload, dict):
        return ValidationResult(
            spec_type="agent",
            is_valid=False,
            issues=["el payload del agente debe ser un objeto JSON"],
        )

    system_prompt = payload.get("system_prompt")
    tools = payload.get("tools")

    if not isinstance(system_prompt, str) or not system_prompt.strip():
        issues.append("'system_prompt' debe ser una cadena no vacía")
    if not isinstance(tools, list) or not tools:
        issues.append("'tools' debe ser una lista no vacía")
    else:
        for idx, tool in enumerate(tools):
            if not isinstance(tool, dict):
                issues.append(f"tools[{idx}]: debe ser un objeto")
                continue
            for field in ("name", "description", "input_schema"):
                if field not in tool:
                    issues.append(f"tools[{idx}]: falta '{field}'")
            schema = tool.get("input_schema")
            if isinstance(schema, dict):
                if schema.get("type") != "object":
                    issues.append(
                        f"tools[{idx}].input_schema.type debe ser 'object'"
                    )
                if "properties" not in schema:
                    issues.append(
                        f"tools[{idx}].input_schema debe incluir 'properties'"
                    )

    return ValidationResult(
        spec_type="agent",
        is_valid=not issues,
        issues=issues,
        suggestions=suggestions,
    )


VALIDATORS = {
    "openapi": _validate_openapi,
    "gherkin": _validate_gherkin,
    "agent": _validate_agent,
}


async def validate_specs(state: SpecState) -> dict:
    """Valida cada spec generado y emite un ValidationResult por tipo.

    También añade entradas ValidationResult(is_valid=False) por cada tipo de spec
    que falló en generación (registrado en state.generation_errors), para que el
    consolidator pueda reportarlas en el README.
    """
    results: list[ValidationResult] = []

    for spec_type, content in state.generated_specs.items():
        validator = VALIDATORS.get(spec_type)
        if validator is None:
            results.append(
                ValidationResult(
                    spec_type=spec_type,
                    is_valid=False,
                    issues=[f"no hay validador registrado para '{spec_type}'"],
                )
            )
            continue
        results.append(validator(content))

    for err in state.generation_errors:
        results.append(
            ValidationResult(
                spec_type=err.spec_type,
                is_valid=False,
                issues=[f"generación fallida: {err.message}"],
            )
        )

    return {"validation_results": results}
