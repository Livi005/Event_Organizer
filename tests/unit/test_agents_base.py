"""Tests para la clase base de agentes."""

import time

import pytest

from eventide.agents.base import AgenteBase, BuzonGlobal, Mensaje


# =============================================================
# AGENTE DE PRUEBA
# =============================================================

class AgenteEco(AgenteBase):
    """Agente que responde a 'ping' con 'pong'."""

    def __init__(self, nombre: str, receptor_respuesta: str | None = None):
        super().__init__(nombre)
        self.recibidos: list[Mensaje] = []
        self.receptor_respuesta = receptor_respuesta

    def manejar_mensaje(self, msg: Mensaje) -> None:
        self.recibidos.append(msg)
        if msg.tipo == "ping" and self.receptor_respuesta:
            self.enviar(self.receptor_respuesta, "pong", {"echo": msg.payload})


# =============================================================
# FIXTURES
# =============================================================

@pytest.fixture(autouse=True)
def limpiar_buzon():
    """Limpia el registro global antes y después de cada test."""
    BuzonGlobal.limpiar()
    yield
    BuzonGlobal.limpiar()


# =============================================================
# TESTS — MENSAJE
# =============================================================

def test_mensaje_basico():
    m = Mensaje(emisor="a", receptor="b", tipo="hola")
    assert m.emisor == "a"
    assert m.receptor == "b"
    assert m.tipo == "hola"
    assert m.payload == {}
    assert m.timestamp is not None


def test_mensaje_con_payload():
    m = Mensaje("a", "b", "datos", {"x": 1, "y": [2, 3]})
    assert m.payload["x"] == 1
    assert m.payload["y"] == [2, 3]


def test_mensaje_repr():
    m = Mensaje("a", "b", "test", {"key": "val"})
    r = repr(m)
    assert "a→b" in r
    assert "tipo=test" in r


# =============================================================
# TESTS — BUZON GLOBAL
# =============================================================

def test_buzon_registrar_y_obtener():
    from queue import Queue
    q = Queue()
    BuzonGlobal.registrar("agente_x", q)
    assert BuzonGlobal.obtener("agente_x") is q


def test_buzon_obtener_inexistente():
    assert BuzonGlobal.obtener("no_existe") is None


def test_buzon_listar():
    from queue import Queue
    BuzonGlobal.registrar("a", Queue())
    BuzonGlobal.registrar("b", Queue())
    nombres = BuzonGlobal.listar()
    assert "a" in nombres
    assert "b" in nombres


# =============================================================
# TESTS — AGENTE BASE
# =============================================================

def test_agente_se_registra_al_crear():
    agente = AgenteEco("test_agente")
    assert BuzonGlobal.obtener("test_agente") is agente.bandeja


def test_agente_start_stop():
    agente = AgenteEco("test_lifecycle")
    assert not agente.running

    agente.start()
    assert agente.running

    time.sleep(0.1)
    agente.stop()
    assert not agente.running


def test_agente_recibe_mensaje():
    agente = AgenteEco("receptor")
    agente.start()
    time.sleep(0.05)

    BuzonGlobal.obtener("receptor").put(
        Mensaje("externo", "receptor", "ping", {"n": 1})
    )
    time.sleep(0.2)

    assert len(agente.recibidos) == 1
    assert agente.recibidos[0].tipo == "ping"
    assert agente.recibidos[0].payload["n"] == 1

    agente.stop()


def test_agente_envia_mensaje():
    receptor = AgenteEco("receptor_2")
    emisor = AgenteEco("emisor_2")
    receptor.start()
    time.sleep(0.05)

    ok = emisor.enviar("receptor_2", "saludo", {"texto": "hola"})
    assert ok is True
    time.sleep(0.2)

    assert len(receptor.recibidos) == 1
    assert receptor.recibidos[0].emisor == "emisor_2"
    assert receptor.recibidos[0].payload["texto"] == "hola"

    receptor.stop()


def test_agente_enviar_a_inexistente():
    agente = AgenteEco("emisor_3")
    ok = agente.enviar("fantasma", "test", {})
    assert ok is False


def test_agente_ping_pong():
    """Test end-to-end: dos agentes se comunican."""
    eco = AgenteEco("eco", receptor_respuesta="cliente")
    cliente = AgenteEco("cliente")

    eco.start()
    cliente.start()
    time.sleep(0.05)

    cliente.enviar("eco", "ping", {"msg": "hola"})
    time.sleep(0.3)

    assert len(eco.recibidos) == 1
    assert eco.recibidos[0].tipo == "ping"

    assert len(cliente.recibidos) == 1
    assert cliente.recibidos[0].tipo == "pong"
    assert cliente.recibidos[0].payload["echo"]["msg"] == "hola"

    eco.stop()
    cliente.stop()


def test_agente_stats():
    agente = AgenteEco("stat_agente")
    agente.start()
    time.sleep(0.05)

    agente.enviar("stat_agente", "test", {})
    time.sleep(0.2)

    stats = agente.stats
    assert stats["nombre"] == "stat_agente"
    assert stats["running"] is True
    assert stats["mensajes_procesados"] >= 1
    assert "uptime_seconds" in stats

    agente.stop()


def test_agente_no_se_puede_instanciar_sin_manejar_mensaje():
    """AgenteBase es abstracta."""
    with pytest.raises(TypeError):
        AgenteBase("test")  # type: ignore


def test_agente_stop_idempotente():
    agente = AgenteEco("stop_idem")
    agente.start()
    time.sleep(0.05)
    agente.stop()
    agente.stop()  # no debe fallar


def test_agente_start_idempotente():
    agente = AgenteEco("start_idem")
    agente.start()
    agente.start()  # no debe crashear
    assert agente.running
    agente.stop()


def test_agente_error_no_mata_loop():
    """Un error en manejar_mensaje no debe detener el agente."""

    class AgenteFallon(AgenteBase):
        def __init__(self):
            super().__init__("fallon")
            self.contador = 0

        def manejar_mensaje(self, msg: Mensaje) -> None:
            self.contador += 1
            if msg.tipo == "boom":
                raise ValueError("error simulado")

    agente = AgenteFallon()
    agente.start()
    time.sleep(0.05)

    agente.enviar("fallon", "boom", {})
    time.sleep(0.2)
    agente.enviar("fallon", "ok", {})
    time.sleep(0.2)

    assert agente.contador == 2
    assert agente.running

    agente.stop()