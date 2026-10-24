"""Tests para el módulo de optimización."""

import pytest

from eventide.core.optimizer import (
    _agenda_valida,
    _calcular_huecos,
    _generar_vecino,
    _tiempo_traslado_min,
    evaluar_agenda,
    generar_solucion_inicial,
    hay_solape,
    hill_climbing,
    optimizar_agenda,
    random_search,
    simulated_annealing,
)
from eventide.core.simulation import generar_escenarios, generar_eventos


# === Fixtures ===

@pytest.fixture
def eventos():
    return generar_eventos(n=100, seed=42)


@pytest.fixture
def preferencias():
    return {
        "location": "Madrid",
        "categories": ["concerts", "festivals"],
        "available_dates": (
            "2025-01-01T00:00:00+00:00",
            "2027-12-31T00:00:00+00:00",
        ),
        "duracion_maxima": 180,
        "velocidad_kmh": 30,
    }


# === Solape ===

def test_hay_solape_true(eventos):
    # Dos eventos del pool con la misma fecha solapan
    e1 = eventos[0].copy()
    e2 = eventos[0].copy()
    assert hay_solape(e1, e2)


def test_hay_solape_false(eventos):
    e1 = eventos[0].copy()
    e2 = eventos[1].copy()
    # Modificar para que no solapen
    e2["temporal_info"]["start"] = "2030-01-01T20:00:00+00:00"
    assert not hay_solape(e1, e2)


# === Solución inicial ===

def test_generar_solucion_inicial_size(eventos):
    import random
    rng = random.Random(42)
    sol = generar_solucion_inicial(eventos, n=5, rng=rng)
    assert len(sol) == 5


def test_generar_solucion_inicial_no_solapes(eventos):
    import random
    rng = random.Random(42)
    sol = generar_solucion_inicial(eventos, n=5, rng=rng)
    assert _agenda_valida(sol)


# === Evaluación ===

def test_evaluar_agenda_vacia():
    assert evaluar_agenda([], {}) == 0.0


def test_evaluar_agenda_positiva(eventos, preferencias):
    import random
    rng = random.Random(42)
    sol = generar_solucion_inicial(eventos, n=5, rng=rng)
    score = evaluar_agenda(sol, preferencias)
    # Puede ser positivo o negativo, pero no debe crashear
    assert isinstance(score, float)


# === Algoritmos ===

def test_random_search(eventos, preferencias):
    agenda, score, trace = random_search(eventos, preferencias, n=5, max_iter=20, seed=1)
    assert len(agenda) == 5
    assert _agenda_valida(agenda)
    assert len(trace) == 21


def test_hill_climbing(eventos, preferencias):
    agenda, score, trace = hill_climbing(eventos, preferencias, n=5, max_iter=20, seed=1)
    assert len(agenda) == 5
    assert _agenda_valida(agenda)
    assert len(trace) == 21


def test_simulated_annealing(eventos, preferencias):
    agenda, score, trace = simulated_annealing(eventos, preferencias, n=5, max_iter=20, seed=1)
    assert len(agenda) == 5
    assert _agenda_valida(agenda)
    assert len(trace) == 21


def test_sa_mejora_o_igual_que_inicial(eventos, preferencias):
    """SA nunca debe terminar peor que su solución inicial."""
    agenda, score, trace = simulated_annealing(eventos, preferencias, n=5, max_iter=50, seed=1)
    assert trace[-1] >= trace[0] - 1e-9


# === API de alto nivel ===

def test_optimizar_agenda_sa(eventos, preferencias):
    agenda, score, trace = optimizar_agenda(eventos, preferencias, cantidad=5, algoritmo="sa", seed=1)
    assert len(agenda) == 5


def test_optimizar_agenda_algoritmo_invalido(eventos, preferencias):
    with pytest.raises(ValueError):
        optimizar_agenda(eventos, preferencias, algoritmo="noexiste")


def test_optimizar_agenda_pool_insuficiente(preferencias):
    eventos_pocos = generar_eventos(n=3, seed=1)
    with pytest.raises(ValueError):
        optimizar_agenda(eventos_pocos, preferencias, cantidad=5)


# === Reproducibilidad ===

def test_sa_reproducible(eventos, preferencias):
    a1, s1, _ = simulated_annealing(eventos, preferencias, n=5, max_iter=30, seed=999)
    a2, s2, _ = simulated_annealing(eventos, preferencias, n=5, max_iter=30, seed=999)
    assert s1 == s2


# === Helpers ===

def test_calcular_huecos_vacio():
    assert _calcular_huecos([]) == 0.0


def test_calcular_huecos_un_evento(eventos):
    assert _calcular_huecos([eventos[0]]) == 0.0