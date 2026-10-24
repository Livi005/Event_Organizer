"""Tests para el AgenteNarrador."""

import time

import pytest

from eventide.agents.base import AgenteBase, BuzonGlobal, Mensaje
from eventide.agents.narrador import AgenteNarrador
from eventide.core.simulation import generar_eventos


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
def narrador_fallback():
    """Narrador en modo fallback (sin LLM, para tests rápidos y deterministas)."""
    BuzonGlobal.limpiar()
    agente = AgenteNarrador(nombre="narrador", usar_llm=False)
    agente.start()
    time.sleep(0.2)
    yield agente
    agente.stop()


@pytest.fixture
def narrador_limpio(narrador_fallback):
    """Narrador con cache limpia antes y después de cada test."""
    narrador_fallback._cache.clear()
    yield narrador_fallback
    narrador_fallback._cache.clear()


@pytest.fixture
def cliente():
    c = ClienteCaptura(nombre=f"cliente_{time.time_ns()}")
    c.start()
    time.sleep(0.1)
    yield c
    c.stop()


@pytest.fixture
def agenda_ejemplo():
    eventos = generar_eventos(n=5, seed=42)
    return eventos


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
    }


# =============================================================
# TESTS
# =============================================================

def test_narrador_arranca(narrador_fallback):
    assert narrador_fallback.running
    assert narrador_fallback.usar_llm is False  # modo fallback


def test_narrar_agenda_vacia(narrador_fallback, preferencias, cliente):
    narrador_fallback.enviar(
        "narrador", "narrar",
        {
            "agenda": [],
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert respuesta.tipo == "narracion_lista"
    # El mensaje debe indicar que no se encontraron eventos
    texto = respuesta.payload["texto"].lower()
    assert (
        "no encontre" in texto
        or "vaya" in texto
        or "amplie la busqueda" in texto
    )
    assert respuesta.payload["fuente"] == "fallback"


def test_narrar_agenda_simple(narrador_fallback, agenda_ejemplo, preferencias, cliente):
    narrador_fallback.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    assert respuesta is not None
    assert respuesta.tipo == "narracion_lista"

    texto = respuesta.payload["texto"]
    assert len(texto) > 50
    assert respuesta.payload["fuente"] == "fallback"


def test_fallback_incluye_titulos(narrador_fallback, agenda_ejemplo, preferencias, cliente):
    narrador_fallback.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    texto = respuesta.payload["texto"]

    titulos = [ev["basic_info"]["title"] for ev in agenda_ejemplo]
    mencionados = sum(1 for t in titulos if t in texto)
    assert mencionados >= len(titulos) // 2


def test_fallback_incluye_titulos_y_estructura(
    narrador_fallback, agenda_ejemplo, preferencias, cliente
):
    """
    El fallback debe incluir los titulos de los eventos y una estructura
    reconocible (saludo + eventos + razon + cierre).
    """
    narrador_fallback.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    respuesta = cliente.esperar_mensaje(timeout=5.0)
    texto = respuesta.payload["texto"]

    # Debe mencionar al menos un titulo real
    titulos = [ev["basic_info"]["title"] for ev in agenda_ejemplo]
    mencionados = sum(1 for t in titulos if t in texto)
    assert mencionados >= 1

    # Debe tener la estructura del fallback
    assert "Por que te lo propongo" in texto
    assert "Si deseas cambiar algo" in texto

def test_cache_funciona(narrador_limpio, agenda_ejemplo, preferencias, cliente):
    """Primera llamada cache_miss, segunda cache_hit."""
    narrador = narrador_limpio

    # Primera llamada (cache vacía)
    narrador.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    r1 = cliente.esperar_mensaje(timeout=5.0)
    assert r1 is not None
    assert r1.payload["cache_hit"] is False

    # Segunda llamada idéntica → cache hit
    narrador.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    r2 = cliente.esperar_mensaje(timeout=5.0)
    assert r2 is not None
    assert r2.payload["cache_hit"] is True
    assert r2.payload["texto"] == r1.payload["texto"]


def test_limpiar_cache(narrador_limpio, agenda_ejemplo, preferencias, cliente):
    narrador = narrador_limpio

    # Llenar cache
    narrador.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    cliente.esperar_mensaje(timeout=5.0)

    # Limpiar
    narrador.enviar("narrador", "limpiar_cache", {"respuesta_a": cliente.nombre})
    r = cliente.esperar_mensaje(timeout=5.0)
    assert r.payload["ok"] is True

    # Ahora la próxima llamada NO debe ser cache hit
    narrador.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    r2 = cliente.esperar_mensaje(timeout=5.0)
    assert r2.payload["cache_hit"] is False


def test_stats_narrador(narrador_fallback, agenda_ejemplo, preferencias, cliente):
    narrador_fallback.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda_ejemplo,
            "preferencias": preferencias,
            "respuesta_a": cliente.nombre,
        },
    )
    cliente.esperar_mensaje(timeout=5.0)

    narrador_fallback.enviar(
        "narrador", "stats",
        {"respuesta_a": cliente.nombre},
    )
    r = cliente.esperar_mensaje(timeout=5.0)
    assert r.tipo == "stats_narrador"
    assert r.payload["narraciones_realizadas"] >= 1
    assert r.payload["usar_llm"] is False


def test_hash_determinista():
    """El hash debe ser determinista para misma agenda."""
    agenda1 = [{"id": "a"}, {"id": "b"}]
    agenda2 = [{"id": "b"}, {"id": "a"}]  # mismo conjunto, distinto orden
    prefs = {"location": "Madrid", "categories": ["rock"]}

    h1 = AgenteNarrador._hash_agenda(agenda1, prefs)
    h2 = AgenteNarrador._hash_agenda(agenda2, prefs)
    assert h1 == h2


def test_hash_diferente_para_agendas_diferentes():
    prefs = {"location": "Madrid", "categories": ["rock"]}
    h1 = AgenteNarrador._hash_agenda([{"id": "a"}], prefs)
    h2 = AgenteNarrador._hash_agenda([{"id": "b"}], prefs)
    assert h1 != h2