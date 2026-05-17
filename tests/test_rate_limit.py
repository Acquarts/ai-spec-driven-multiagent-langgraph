"""Tests del rate limiter en memoria."""

from __future__ import annotations

import time

from src.rate_limit import check_rate_limit, reset


def test_permite_dentro_del_limite():
    reset("ip-test-1")
    for _ in range(3):
        permitido, _ = check_rate_limit("ip-test-1", max_requests=3, window_seconds=60)
        assert permitido


def test_bloquea_cuando_excede():
    reset("ip-test-2")
    for _ in range(2):
        check_rate_limit("ip-test-2", max_requests=2, window_seconds=60)
    permitido, espera = check_rate_limit("ip-test-2", max_requests=2, window_seconds=60)
    assert not permitido
    assert espera > 0


def test_libera_tras_ventana():
    reset("ip-test-3")
    # ventana de 1 segundo, max 1 petición
    check_rate_limit("ip-test-3", max_requests=1, window_seconds=1)
    permitido, _ = check_rate_limit("ip-test-3", max_requests=1, window_seconds=1)
    assert not permitido

    time.sleep(1.1)
    permitido, _ = check_rate_limit("ip-test-3", max_requests=1, window_seconds=1)
    assert permitido


def test_claves_distintas_son_independientes():
    reset("ip-test-a")
    reset("ip-test-b")
    for _ in range(3):
        check_rate_limit("ip-test-a", max_requests=3, window_seconds=60)
    # la 'a' está al límite, la 'b' libre
    a_permitido, _ = check_rate_limit("ip-test-a", max_requests=3, window_seconds=60)
    b_permitido, _ = check_rate_limit("ip-test-b", max_requests=3, window_seconds=60)
    assert not a_permitido
    assert b_permitido
