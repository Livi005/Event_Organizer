"""Entry point para arrancar la API con agentes."""

from __future__ import annotations

import atexit
import time

from eventide.agents.base import BuzonGlobal
from eventide.agents.buscador import AgenteBuscador
from eventide.agents.narrador import AgenteNarrador
from eventide.agents.optimizador import AgenteOptimizador
from eventide.api.server import run
from eventide.logging_config import get_logger

logger = get_logger(__name__)


def _arrancar_agentes() -> list:
    """Arranca los agentes esenciales para la API."""
    logger.info("Arrancando agentes de la API...")

    buscador = AgenteBuscador(nombre="buscador", n_eventos_sinteticos=200)
    optimizador = AgenteOptimizador(nombre="optimizador")
    narrador = AgenteNarrador(nombre="narrador", usar_llm=True)

    agentes = [buscador, optimizador, narrador]
    for a in agentes:
        a.start()

    # Esperar a que el buscador termine setup() (carga modelo)
    logger.info("Esperando setup() del buscador...")
    inicio = time.time()
    while buscador.embedder is None and time.time() - inicio < 120:
        time.sleep(0.5)

    if buscador.embedder is None:
        raise RuntimeError("Timeout esperando setup() del buscador")

    logger.info(
        f"✅ Agentes listos: {BuzonGlobal.listar()}. "
        f"Eventos: {buscador.embedder.num_events}"
    )
    return agentes


def main() -> None:
    logger.info("=" * 60)
    logger.info("Eventide API")
    logger.info("=" * 60)

    agentes = _arrancar_agentes()

    def _shutdown():
        logger.info("Deteniendo agentes...")
        for a in agentes:
            a.stop()

    atexit.register(_shutdown)

    run(host="0.0.0.0", port=8502, debug=False)


if __name__ == "__main__":
    main()