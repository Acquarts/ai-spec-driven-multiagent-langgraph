"""Nodo consolidate — escribe los specs generados en disco y renderiza un README."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import OUTPUT_DIR
from src.state import SpecState, ValidationResult


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_openapi(out_dir: Path, content: str) -> list[str]:
    path = out_dir / "openapi.yaml"
    path.write_text(content, encoding="utf-8")
    return [path.name]


def _write_gherkin(out_dir: Path, content: str) -> list[str]:
    features_dir = out_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    files = json.loads(content)
    written: list[str] = []
    for filename, body in files.items():
        # Defensa: evita path traversal desde un nombre de archivo hostil.
        safe_name = Path(filename).name
        path = features_dir / safe_name
        path.write_text(body, encoding="utf-8")
        written.append(f"features/{safe_name}")
    return written


def _write_agent(out_dir: Path, content: str) -> list[str]:
    agent_dir = out_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(content)
    prompt_path = agent_dir / "system_prompt.md"
    tools_path = agent_dir / "tools.json"
    prompt_path.write_text(payload["system_prompt"], encoding="utf-8")
    tools_path.write_text(
        json.dumps(payload["tools"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return ["agent/system_prompt.md", "agent/tools.json"]


WRITERS = {
    "openapi": _write_openapi,
    "gherkin": _write_gherkin,
    "agent": _write_agent,
}


def _render_readme(
    state: SpecState,
    written_files: dict[str, list[str]],
    out_dir: Path,
) -> str:
    sr = state.structured_requirements
    lines: list[str] = []
    lines.append(f"# Specs generados — {out_dir.name}")
    lines.append("")
    if sr is not None:
        lines.append(f"**Dominio:** {sr.domain}")
        lines.append("")
        lines.append(f"**Resumen:** {sr.raw_summary}")
        lines.append("")
        lines.append("## Requisitos extraídos")
        lines.append("")
        lines.append(f"- **Entidades:** {', '.join(sr.entities) or '_ninguna_'}")
        lines.append(f"- **Acciones:** {', '.join(sr.actions) or '_ninguna_'}")
        lines.append(f"- **Restricciones:** {', '.join(sr.constraints) or '_ninguna_'}")
        lines.append(
            f"- **Integraciones:** {', '.join(sr.integrations) or '_ninguna_'}"
        )
        lines.append("")

    lines.append("## Tipos de spec generados")
    lines.append("")
    if state.spec_types:
        for spec_type in state.spec_types:
            lines.append(f"- `{spec_type}`")
    else:
        lines.append("- _ninguno_")
    lines.append("")

    lines.append("## Resultados de validación")
    lines.append("")
    if state.validation_results:
        for result in state.validation_results:
            status = "[OK]" if result.is_valid else "[FALLA]"
            lines.append(f"### {status} `{result.spec_type}`")
            if result.issues:
                lines.append("")
                lines.append("**Problemas:**")
                for issue in result.issues:
                    lines.append(f"- {issue}")
            if result.suggestions:
                lines.append("")
                lines.append("**Sugerencias:**")
                for s in result.suggestions:
                    lines.append(f"- {s}")
            lines.append("")
    else:
        lines.append("_Sin resultados de validación registrados._")
        lines.append("")

    lines.append("## Índice de archivos")
    lines.append("")
    for spec_type, files in written_files.items():
        lines.append(f"### `{spec_type}`")
        for f in files:
            lines.append(f"- [{f}]({f})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_summary(
    state: SpecState,
    written_files: dict[str, list[str]],
    out_dir: Path,
) -> str:
    total_files = sum(len(v) for v in written_files.values()) + 1  # +README
    valid = sum(1 for r in state.validation_results if r.is_valid)
    total = len(state.validation_results)
    return (
        f"Se escribieron {total_files} archivos en {out_dir}. "
        f"Validación: {valid}/{total} spec(s) pasaron."
    )


async def consolidate(state: SpecState) -> dict:
    out_root = Path(OUTPUT_DIR)
    out_dir = out_root / _timestamp()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, list[str]] = {}
    write_errors: list[ValidationResult] = []

    for spec_type, content in state.generated_specs.items():
        writer = WRITERS.get(spec_type)
        if writer is None:
            continue
        try:
            written[spec_type] = writer(out_dir, content)
        except Exception as exc:  # noqa: BLE001
            write_errors.append(
                ValidationResult(
                    spec_type=spec_type,
                    is_valid=False,
                    issues=[f"falló la escritura de {spec_type}: {exc}"],
                )
            )

    readme = _render_readme(state, written, out_dir)
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    summary = _format_summary(state, written, out_dir)

    result: dict = {
        "output_path": str(out_dir),
        "final_summary": summary,
    }
    if write_errors:
        result["validation_results"] = write_errors
    return result
