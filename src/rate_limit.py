"""Rate limiter sencillo en memoria, por clave (típicamente IP del cliente).

Limitaciones conocidas:
- El estado vive en el proceso. Si Cloud Run escala a N instancias, el límite
  efectivo es N * RATE_LIMIT_REQUESTS por ventana. Para tráfico bajo es
  suficiente; para multi-instancia real harían falta Redis/Memorystore.
- No hay limpieza periódica del diccionario — solo limpia al consultar.
  Bien para volúmenes moderados.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque

_lock = threading.Lock()
_hits: dict[str, Deque[float]] = defaultdict(deque)


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Devuelve (permitido, segundos_para_proximo_intento).

    Si permitido es True, segundos_para_proximo_intento será 0.
    Si False, indica cuánto debe esperar el cliente antes de retry.
    """
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        bucket = _hits[key]
        # Limpia hits fuera de la ventana.
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            # El primer hit aún dentro de la ventana define cuándo se libera espacio.
            wait = int(bucket[0] + window_seconds - now) + 1
            return False, max(wait, 1)

        bucket.append(now)
        return True, 0


def reset(key: str) -> None:
    """Limpia el contador para una clave (útil en tests)."""
    with _lock:
        _hits.pop(key, None)
