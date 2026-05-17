"""Configuración centralizada: IDs de modelo, política de reintentos, cliente Anthropic compartido."""

from __future__ import annotations

import os
import time
import uuid
from functools import lru_cache

from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AsyncAnthropic,
    InternalServerError,
    RateLimitError,
)
from dotenv import load_dotenv
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.cost import global_tracker
from src.logging_setup import get_logger

_log = get_logger(__name__)

# Carga .env desde la raíz del proyecto independientemente del cwd.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

GENERATION_MODEL = os.getenv("GENERATION_MODEL", "claude-opus-4-7")
UTILITY_MODEL = os.getenv("UTILITY_MODEL", "claude-haiku-4-5-20251001")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# Password compartido para acceder a la UI Streamlit.
# Si está vacío, no se exige autenticación (útil en desarrollo local).
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

# Rate limit: peticiones por IP en una ventana de tiempo.
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Tamaño máximo (en caracteres) del input de requisitos.
MAX_REQUIREMENTS_CHARS = int(os.getenv("MAX_REQUIREMENTS_CHARS", "10000"))

MAX_RETRIES = 3
RETRY_WAIT_MIN = 2
RETRY_WAIT_MAX = 30


@lru_cache(maxsize=1)
def get_client() -> AsyncAnthropic:
    raw = os.getenv("ANTHROPIC_API_KEY", "")
    # Quita espacios en blanco y comillas envolventes accidentales de los valores .env.
    api_key = raw.strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY no está configurada. Copia .env.example a .env y añade tu clave."
        )
    if "..." in api_key or not api_key.startswith("sk-"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY parece mal formada (contiene '...' o le falta el prefijo 'sk-'). "
            "Reemplaza el placeholder de .env por una clave real de console.anthropic.com."
        )
    return AsyncAnthropic(api_key=api_key)


def retry_policy() -> AsyncRetrying:
    """Backoff exponencial solo para fallos *transitorios*.

    Excluye AuthenticationError, PermissionDeniedError, BadRequestError, etc. —
    reintentar un 4xx es latencia desperdiciada.
    """
    return AsyncRetrying(
        retry=retry_if_exception_type(
            (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
        ),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        stop=stop_after_attempt(MAX_RETRIES),
        reraise=True,
    )


async def call_model(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    node: str | None = None,
) -> str:
    """Llamada texto-in/texto-out con reintento. Devuelve la respuesta del modelo.

    Cada llamada emite un log estructurado con node, model, tokens y latencia.
    El argumento `node` es opcional pero recomendado — facilita filtrar en
    Cloud Logging por nodo del grafo.

    Nota: `temperature` no se expone a propósito. Los modelos Claude 4.x
    (p. ej. Opus 4.7) lo han deprecado, y nuestros system prompts ya
    restringen el formato de salida de forma estricta.
    """
    client = get_client()
    request_id = str(uuid.uuid4())[:8]
    started = time.monotonic()

    _log.info(
        "llm_call_start",
        extra={
            "request_id": request_id,
            "node": node or "unknown",
            "model": model,
            "max_tokens": max_tokens,
            "input_chars": len(system) + len(user),
        },
    )

    try:
        async for attempt in retry_policy():
            with attempt:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                cost_entry = global_tracker().add(
                    model=model,
                    tokens_in=response.usage.input_tokens,
                    tokens_out=response.usage.output_tokens,
                )
                _log.info(
                    "llm_call_ok",
                    extra={
                        "request_id": request_id,
                        "node": node or "unknown",
                        "model": model,
                        "tokens_in": response.usage.input_tokens,
                        "tokens_out": response.usage.output_tokens,
                        "usd": round(cost_entry.usd, 6),
                        "stop_reason": response.stop_reason,
                        "latency_ms": int((time.monotonic() - started) * 1000),
                        "output_chars": len(text),
                    },
                )
                # El modelo se quedó sin presupuesto de tokens → respuesta truncada.
                # Lanzar permite que el nodo lo capture y registre como GenerationError
                # con un mensaje claro, en vez de devolver YAML/JSON cortado.
                if response.stop_reason == "max_tokens":
                    raise RuntimeError(
                        f"el modelo se quedó sin presupuesto de tokens "
                        f"(max_tokens={max_tokens}, tokens_out={response.usage.output_tokens}). "
                        "La respuesta está truncada. Reduce el tamaño de los requisitos "
                        "o sube max_tokens en el nodo."
                    )
                return text
        raise RuntimeError("retry_policy agotada sin retornar")
    except Exception as exc:
        _log.warning(
            "llm_call_failed",
            extra={
                "request_id": request_id,
                "node": node or "unknown",
                "model": model,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
                "latency_ms": int((time.monotonic() - started) * 1000),
            },
        )
        raise


def strip_code_fences(text: str) -> str:
    """Elimina fences markdown (```yaml, ```json, ```) al principio/final si están presentes."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def parse_json_response(text: str):
    """Parsea el primer valor JSON en `text`, tolerando prosa antes/después.

    La API de Claude a veces envuelve el JSON en fences o añade una línea final
    tipo "Espero que ayude". `json.loads` rechaza contenido sobrante, pero
    `JSONDecoder.raw_decode` parsea un valor y devuelve la posición donde acabó.
    """
    import json

    cleaned = strip_code_fences(text)

    # Salta cualquier preámbulo antes del primer '{' o '['.
    first_obj = cleaned.find("{")
    first_arr = cleaned.find("[")
    candidates = [i for i in (first_obj, first_arr) if i != -1]
    if not candidates:
        raise json.JSONDecodeError("no se encontró ningún objeto o array JSON", cleaned, 0)
    start = min(candidates)
    decoder = json.JSONDecoder()
    payload, _end = decoder.raw_decode(cleaned[start:])
    return payload
