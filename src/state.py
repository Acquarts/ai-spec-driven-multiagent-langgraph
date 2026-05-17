"""SpecState y modelos Pydantic de apoyo.

Los campos `generated_specs`, `validation_results` y `generation_errors` usan
reducers de LangGraph para que las ramas paralelas lanzadas con `Send` se
fusionen sin conflictos.
"""

from __future__ import annotations

import operator
from typing import Annotated

from pydantic import BaseModel, Field


class StructuredRequirements(BaseModel):
    domain: str
    entities: list[str]
    actions: list[str]
    constraints: list[str]
    integrations: list[str]
    raw_summary: str


class ValidationResult(BaseModel):
    spec_type: str
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class GenerationError(BaseModel):
    spec_type: str
    message: str


class SpecState(BaseModel):
    # Entrada
    raw_requirements: str

    # Procesado
    structured_requirements: StructuredRequirements | None = None
    spec_types: list[str] = Field(default_factory=list)

    # Specs generados (poblados en paralelo — fusionados por unión de diccionario)
    generated_specs: Annotated[dict[str, str], operator.or_] = Field(
        default_factory=dict
    )

    # Errores de las ramas de generación (append seguro en paralelo)
    generation_errors: Annotated[list[GenerationError], operator.add] = Field(
        default_factory=list
    )

    # Resultados de validación (append seguro en paralelo)
    validation_results: Annotated[list[ValidationResult], operator.add] = Field(
        default_factory=list
    )

    # Salida
    output_path: str | None = None
    final_summary: str | None = None
