"""Tests para el módulo de simulación."""

import pytest

from eventide.core.simulation import (
    CIUDADES_ES,
    PERFILES,
    generar_eventos,
    generar_escenarios,
    generar_perfiles_usuario,
    simular_agenda_para_perfil,
    monte_carlo_runs,
    resumen_monte_carlo,
)


# === Eventos ===

def test_generar_eventos_cantidad():
    eventos = generar_eventos(n=50, seed=1)
    assert len(eventos) == 50


def test_generar_eventos_estructura():
    eventos = generar_eventos(n=10, seed=1)
    for ev in eventos:
        assert "id" in ev
        assert "basic_info" in ev
        assert "classification" in ev
        assert "temporal_info" in ev
        assert "spatial_info" in ev
        assert ev["classification"]["primary_category"] in {
            "concerts", "theater", "sports", "arts",
            "technology", "food", "literature", "wellness",
            "festivals", "conferences",
        }


def test_generar_eventos_reproducible():
    a = generar_eventos(n=20, seed=42)
    b = generar_eventos(n=20, seed=42)
    assert [e["id"] for e in a] == [e["id"] for e in b]


def test_generar_eventos_coordenadas_validas():
    eventos = generar_eventos(n=30, seed=1)
    for ev in eventos:
        loc = ev["spatial_info"]["venue"]["location"]
        assert -90 <= loc["latitude"] <= 90
        assert -180 <= loc["longitude"] <= 180


# === Escenarios ===

def test_generar_escenarios():
    escenarios = generar_escenarios(n=15, seed=2)
    assert len(escenarios) == 15
    for esc in escenarios:
        assert esc["location"] in CIUDADES_ES
        assert isinstance(esc["categories"], list)
        assert len(esc["categories"]) >= 1
        assert "available_dates" in esc
        assert len(esc["available_dates"]) == 2


# === Perfiles ===

def test_generar_perfiles():
    perfiles = generar_perfiles_usuario()
    assert "joven_fiestero" in perfiles
    assert "familia" in perfiles
    assert len(perfiles) == 6


def test_simular_agenda_para_perfil():
    eventos = generar_eventos(n=100, seed=1)
    agenda = simular_agenda_para_perfil("joven_fiestero", eventos, seed=1)
    assert len(agenda) <= 5
    for ev in agenda:
        assert ev["classification"]["primary_category"] in ["concerts", "festivals"]


def test_simular_agenda_perfil_invalido():
    eventos = generar_eventos(n=10, seed=1)
    with pytest.raises(ValueError):
        simular_agenda_para_perfil("perfil_falso", eventos)


# === Monte Carlo ===

def test_monte_carlo_basico():
    def f(seed):
        import random
        random.seed(seed)
        return {"score": random.random()}

    resultados = monte_carlo_runs(f, n_runs=10)
    assert len(resultados) == 10
    assert all(r["status"] == "ok" for r in resultados)


def test_monte_carlo_captura_errores():
    def f(seed):
        if seed == 3:
            raise ValueError("error simulado")
        return {"score": seed}

    resultados = monte_carlo_runs(f, n_runs=5)
    assert resultados[3]["status"] == "error"
    assert "error simulado" in resultados[3]["error"]


def test_resumen_monte_carlo():
    def f(seed):
        return {"score": seed * 10}

    resultados = monte_carlo_runs(f, n_runs=5)
    resumen = resumen_monte_carlo(resultados, extractor=lambda r: r["score"])
    assert resumen["n_valid"] == 5
    assert resumen["min"] == 0
    assert resumen["max"] == 40
    assert resumen["mean"] == 20.0