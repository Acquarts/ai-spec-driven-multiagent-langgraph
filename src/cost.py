"""Tracking de coste: cuenta tokens por modelo y los convierte a USD.

Precios de Anthropic (USD por millón de tokens) a fecha 2026-05.
Actualizar cuando cambien: https://www.anthropic.com/pricing
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# USD por 1M de tokens. Tupla = (input, output).
_PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

# Fallback razonable si el modelo no está en la tabla (usar precio Opus = conservador).
_PRICE_FALLBACK = (15.0, 75.0)


@dataclass
class CostEntry:
    model: str
    tokens_in: int
    tokens_out: int
    usd: float


@dataclass
class CostTracker:
    """Acumulador thread-safe de coste por sesión.

    Cada instancia rastrea una sesión independiente. La app crea una por
    cada ejecución del pipeline (vive en st.session_state).
    """

    entries: list[CostEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, model: str, tokens_in: int, tokens_out: int) -> CostEntry:
        price_in, price_out = _PRICES_PER_1M.get(model, _PRICE_FALLBACK)
        usd = (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
        entry = CostEntry(model=model, tokens_in=tokens_in, tokens_out=tokens_out, usd=usd)
        with self._lock:
            self.entries.append(entry)
        return entry

    @property
    def total_usd(self) -> float:
        with self._lock:
            return sum(e.usd for e in self.entries)

    @property
    def total_tokens_in(self) -> int:
        with self._lock:
            return sum(e.tokens_in for e in self.entries)

    @property
    def total_tokens_out(self) -> int:
        with self._lock:
            return sum(e.tokens_out for e in self.entries)

    def summary(self) -> dict:
        """Resumen serializable para logs/UI."""
        with self._lock:
            return {
                "calls": len(self.entries),
                "tokens_in": sum(e.tokens_in for e in self.entries),
                "tokens_out": sum(e.tokens_out for e in self.entries),
                "usd": round(sum(e.usd for e in self.entries), 4),
                "by_model": self._by_model(),
            }

    def _by_model(self) -> dict:
        agg: dict[str, dict] = {}
        for e in self.entries:
            slot = agg.setdefault(
                e.model, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "usd": 0.0}
            )
            slot["calls"] += 1
            slot["tokens_in"] += e.tokens_in
            slot["tokens_out"] += e.tokens_out
            slot["usd"] += e.usd
        for slot in agg.values():
            slot["usd"] = round(slot["usd"], 4)
        return agg


# Tracker global por proceso. La app lo usa cuando no quiere/puede pasar uno
# explícitamente al call_model (p. ej. para el total de vida del contenedor).
_global_tracker = CostTracker()


def global_tracker() -> CostTracker:
    return _global_tracker
