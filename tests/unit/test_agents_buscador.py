"""Tests para el AgenteBuscador."""

import time

import pytest

from eventide.agents.base import AgenteBase, BuzonGlobal, Mensaje
from eventide.agents.buscador import AgenteBuscador
from eventide.core.embedding import EventEmbedder


# =============================================================
# CLIENTE
# =============================================================

class ClienteCaptura(AgenteBase):
    def __init__(self, nombre: str = "cliente"):
        super().__init__(nombre)
        self.mensajes: list[Mensaje] = []

    def manejar_mensaje(self, msg: Mensaje) -> None:
        self.mensajes.append(msg)

    def esperar_mensaje(self, timeout: float = 15.0) -> Mensaje | None:
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
def buscador():
    """Buscador compartido para todos los tests del modulo."""
    EventEmbedder.reset()
    BuzonGlobal.limpiar()

    agente = AgenteBuscador(
        nombre="buscador",
        usar_datos_sinteticos=True,
        n_eventos_sinteticos=50,
    )
    agente.start()

    # Esperar a que el flag ready este activo (setup completo)
    inicio = time.time()
    while not agente.ready and time.time() - inicio < 120:
        time.sleep(0.5)

    if not agente.ready:
        raise RuntimeError("Timeout esperando setup() del buscador")

    # Margen extra para que el loop ya este escuchando
    time.sleep(0.5)

    yield agente

    agente.stop()
    EventEmbedder.reset()


@pytest.fixture
def cliente():
    c = ClienteCaptura(nombre=f"cliente_{time.time_ns()}")
    c.start()
    time.sleep(0.2)
    yield c
    c.stop()


# =============================================================
# TESTS
# =============================================================

def test_buscador_arranca(buscador):
    assert buscador.running
    assert buscador.ready
    assert buscador.embedder is not None
    assert buscador.embedder.num_events == 50


def test_buscador_registrado_en_buzon(buscador):
    assert BuzonGlobal.obtener("buscador") is buscador.bandeja


def test_buscar_simple(buscador, cliente):
    ok = buscador.enviar(
        "buscador", "buscar",
        {"query": "concierto", "k": 5, "respuesta_a": cliente.nombre},
    )
    assert ok is True

    respuesta = cliente.esperar_mensaje(timeout=15.0)
    assert respuesta is not None, "El buscador no respondio en 15s"
    assert respuesta.tipo == "resultados_busqueda"
    assert respuesta.payload["query"] == "concierto"
    assert respuesta.payload["total"] <= 5
    assert isinstance(respuesta.payload["resultados"], list)


def test_buscar_con_ciudad(buscador, cliente):
    buscador.enviar(
        "buscador", "buscar",
        {"query": "evento", "ciudad": "Madrid", "k": 10, "respuesta_a": cliente.nombre},
    )

    respuesta = cliente.esperar_mensaje(timeout=15.0)
    assert respuesta is not None

    resultados = respuesta.payload["resultados"]
    for r in resultados:
        assert r["spatial_info"]["area"]["city"] == "Madrid"


def test_buscar_query_vacia(buscador, cliente):
    buscador.enviar(
        "buscador", "buscar",
        {"query": "", "respuesta_a": cliente.nombre},
    )

    respuesta = cliente.esperar_mensaje(timeout=15.0)
    assert respuesta is not None
    assert respuesta.payload["total"] == 0
    assert "error" in respuesta.payload


def test_buscar_sin_respuesta_a(buscador):
    ok = buscador.enviar("buscador", "buscar", {"query": "test"})
    assert ok is True
    time.sleep(0.5)
    assert buscador.running


def test_stats_buscador(buscador, cliente):
    buscador.enviar("buscador", "stats", {"respuesta_a": cliente.nombre})

    respuesta = cliente.esperar_mensaje(timeout=15.0)
    assert respuesta is not None
    assert respuesta.tipo == "stats_buscador"
    assert respuesta.payload["num_eventos"] == 50
    assert respuesta.payload["num_shards"] >= 1
    assert respuesta.payload["ready"] is True


def test_buscador_ignora_tipos_desconocidos(buscador):
    buscador.enviar("buscador", "tipo_raro", {})
    time.sleep(0.3)
    assert buscador.running
