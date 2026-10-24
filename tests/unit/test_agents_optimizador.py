"""Tests para el AgenteOptimizador."""

import time

import pytest

from eventide.agents.base import AgenteBase, BuzonGlobal, Mensaje
from eventide.agents.optimizador import AgenteOptimizador
from eventide.core.simulation import generar_escenarios, generar_eventos


# =============================================================
# CLIENTE
# =============================================================

class ClienteCaptura(AgenteBase):
    def __init__(self, nombre: str = "cliente"):
        super().__init__(nombre)
        self.mensajes: list[Mensaje] = []

    def manejar_mensaje(self, msg: Mensaje) -> None:
        self.mensajes.append(msg)

    def esperar_mensaje(self, timeout: float = 5.0) -> Mensaje | None:
        inicio = time.time()
        while time.time() - inicio < timeout:
            if self.mensajes:
                return self.mensajes.pop(0)
            time.sleep(0.05)
        return None


# =============================================================
# FIXTURES
# =============================================================

@pytest.fixture(scope="module")
def optimizador():
    BuzonGlobal.limpiar()
    agente = AgenteOptimizador(nombre="optimizador")
    agente.start()
    time.sleep(0.2)
    yield agente
    agente.stop()


@pytest.fixture(scope="module")
def eventos():
    return generar_eventos(n=100, seed=42)


@pytest.fixture(scope="module")
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


@pytest.fixture
def cliente():
    c = ClienteCaptura(nombre=f"cliente_{time.time_ns()}")
    c.start()
    time.sleep(0.1)
    yield c
    c.stop()


# =============================================================
# TESTS
# =============================================================

def test_optimizador_arranca(optimizador):
    assert optimizador.running


def test_optimizar_sa(optimizador, eventos, preferencias, cliente):
    ok = optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": eventos,
            "preferencias": preferencias,
            "cantidad": 5,
            "algoritmo": "sa",
            "seed": 42,
            "respuesta_a": cliente.nombre,
        },
    )
    assert ok is True

    respuesta = cliente.esperar_mensaje(timeout=10.0)
    assert respuesta is not None
    assert respuesta.tipo == "agenda_optimizada"

    payload = respuesta.payload
    assert len(payload["agenda"]) == 5
    assert isinstance(payload["score"], float)
    assert payload["algoritmo"] == "sa"
    assert len(payload["trace"]) > 0


def test_optimizar_hc(optimizador, eventos, preferencias, cliente):
    optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": eventos,
            "preferencias": preferencias,
            "algoritmo": "hc",
            "seed": 42,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=10.0)
    assert respuesta is not None
    assert respuesta.payload["algoritmo"] == "hc"


def test_optimizar_random(optimizador, eventos, preferencias, cliente):
    optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": eventos,
            "preferencias": preferencias,
            "algoritmo": "random",
            "seed": 42,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=10.0)
    assert respuesta is not None
    assert respuesta.payload["algoritmo"] == "random"


def test_optimizar_pool_vacio(optimizador, preferencias, cliente):
    optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": [],
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert respuesta.payload["agenda"] == []
    assert "error" in respuesta.payload


def test_optimizar_algoritmo_invalido(optimizador, eventos, preferencias, cliente):
    optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": eventos,
            "preferencias": preferencias,
            "algoritmo": "no_existe",
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert "error" in respuesta.payload


def test_optimizar_pool_insuficiente(optimizador, preferencias, cliente):
    pocos = generar_eventos(n=2, seed=1)
    optimizador.enviar(
        "optimizador", "optimizar",
        {
            "pool": pocos,
            "preferencias": preferencias,
            "cantidad": 5,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert "error" in respuesta.payload


def test_algoritmos_disponibles(optimizador, cliente):
    optimizador.enviar(
        "optimizador", "algoritmos_disponibles",
        {"respuesta_a": cliente.nombre},
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert respuesta.tipo == "algoritmos_disponibles"
    assert set(respuesta.payload["algoritmos"]) == {"random", "hc", "sa"}


def test_stats_optimizador(optimizador, eventos, preferencias, cliente):
    # Hacer varias optimizaciones primero
    for _ in range(3):
        optimizador.enviar(
            "optimizador", "optimizar",
            {
                "pool": eventos,
                "preferencias": preferencias,
                "algoritmo": "sa",
                "seed": 42,
                "respuesta_a": cliente.nombre,
            },
        )
        cliente.esperar_mensaje(timeout=10.0)

    # Ahora pedir stats
    optimizador.enviar(
        "optimizador", "stats",
        {"respuesta_a": cliente.nombre},
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert respuesta.tipo == "stats_optimizador"
    assert respuesta.payload["optimizaciones_realizadas"] >= 3
    assert respuesta.payload["tiempo_medio_ms"] > 0


def test_optimizacion_reproducible(optimizador, eventos, preferencias, cliente):
    """Con la misma seed, el score debe ser idéntico."""
    scores = []
    for _ in range(2):
        optimizador.enviar(
            "optimizador", "optimizar",
            {
                "pool": eventos,
                "preferencias": preferencias,
                "algoritmo": "sa",
                "seed": 123,
                "respuesta_a": cliente.nombre,
            },
        )
        r = cliente.esperar_mensaje(timeout=10.0)
        scores.append(r.payload["score"])

    assert scores[0] == scores[1]