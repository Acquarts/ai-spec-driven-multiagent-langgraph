"""Logging estructurado en formato JSON.

Cloud Run reconoce líneas JSON en stdout/stderr y las muestra como entradas
estructuradas en Cloud Logging (filtrar por campos, agregar por valor, etc.).

Uso:
    from src.logging_setup import get_logger
    log = get_logger(__name__)
    log.info("llm_call", extra={"node": "openapi", "model": "...", "tokens_in": 1234})

Los campos pasados en `extra` se serializan al JSON resultante junto a los
estándar (timestamp, level, message, logger).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_RESERVED_LOG_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formatter que serializa el record como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            # Cloud Logging mapea "severity" automáticamente al nivel.
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Cualquier campo extra que se pasó por `extra={...}` o asignación directa.
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_FIELDS or key.startswith("_"):
                continue
            try:
                json.dumps(value)  # solo incluye lo que sea JSON-serializable
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_logging(level: str | None = None) -> None:
    """Configura el root logger con JsonFormatter. Idempotente."""
    global _configured
    if _configured:
        return

    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_name)

    # Silencia loggers ruidosos de librerías.
    for noisy in ("httpx", "httpcore", "anthropic", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Garantiza que el logging esté configurado y devuelve un logger nombrado."""
    configure_logging()
    return logging.getLogger(name)
