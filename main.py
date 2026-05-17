"""Punto de entrada CLI para el agente de desarrollo dirigido por specs.

Ejemplos:
    python main.py -r "Construir una API REST para tareas con auth JWT..."
    python main.py -f requisitos.txt
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.graph import build_graph
from src.state import SpecState


def _leer_requisitos(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.requirements:
        return args.requirements
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return input("Introduce tus requisitos: ")


async def run(requisitos: str) -> dict:
    graph = build_graph()
    initial = SpecState(raw_requirements=requisitos)
    return await graph.ainvoke(initial)


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description="Agente de Desarrollo Dirigido por Specs"
    )
    parser.add_argument(
        "--requirements", "-r", type=str, help="Requisitos como texto"
    )
    parser.add_argument(
        "--file", "-f", type=str, help="Ruta a un archivo con los requisitos"
    )
    args = parser.parse_args()

    requisitos = _leer_requisitos(args).strip()
    if not requisitos:
        print("error: no se proporcionaron requisitos", file=sys.stderr)
        return 2

    resultado = await run(requisitos)

    output_path = resultado.get("output_path")
    resumen = resultado.get("final_summary")

    print(f"\nSpecs generados en: {output_path}")
    if resumen:
        print(f"\n{resumen}")

    fallidos = [
        r for r in resultado.get("validation_results", [])
        if not getattr(r, "is_valid", True)
    ]
    return 1 if fallidos else 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
