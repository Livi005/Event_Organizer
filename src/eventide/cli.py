"""
Entry point CLI de Eventide.

Uso:
    python -m eventide serve           # arranca la API + agentes
    python -m eventide version         # muestra versión
    python -m eventide agents          # lista agentes registrados
"""

from __future__ import annotations

import argparse
import atexit
import sys
import time

from eventide.agents.base import BuzonGlobal
from eventide.logging_config import get_logger

logger = get_logger(__name__)


def _cmd_serve(args) -> int:
    """Arranca la API con los agentes esenciales."""
    from eventide.agents.buscador import AgenteBuscador
    from eventide.agents.narrador import AgenteNarrador
    from eventide.agents.optimizador import AgenteOptimizador
    from eventide.api.server import run

    logger.info("=" * 60)
    logger.info("Eventide API")
    logger.info("=" * 60)

    # Arrancar agentes
    logger.info("Arrancando agentes...")
    buscador = AgenteBuscador(nombre="buscador", n_eventos_sinteticos=args.eventos)
    optimizador = AgenteOptimizador(nombre="optimizador")
    narrador = AgenteNarrador(nombre="narrador", usar_llm=True)

    agentes = [buscador, optimizador, narrador]
    for a in agentes:
        a.start()

    # Esperar setup del buscador
    logger.info("Esperando setup() del buscador (carga del modelo)...")
    inicio = time.time()
    while buscador.embedder is None and time.time() - inicio < 120:
        time.sleep(0.5)

    if buscador.embedder is None:
        logger.error("Timeout esperando setup() del buscador")
        for a in agentes:
            a.stop()
        return 1

    logger.info(
        f"✅ Agentes listos: {BuzonGlobal.listar()} · "
        f"{buscador.embedder.num_events} eventos indexados"
    )
    logger.info(f"🌐 Escuchando en http://{args.host}:{args.port}")
    logger.info(f"   Prueba: http://localhost:{args.port}/health")
    logger.info("")

    def _shutdown():
        logger.info("Deteniendo agentes...")
        for a in agentes:
            a.stop()

    atexit.register(_shutdown)

    # Arrancar servidor (bloqueante)
    run(host=args.host, port=args.port, debug=args.debug)
    return 0


def _cmd_version(args) -> int:
    from eventide import __version__

    print(f"Eventide {__version__}")
    return 0


def _cmd_agents(args) -> int:
    """Lista agentes registrados (útil para debug)."""
    from eventide.agents.base import BuzonGlobal

    print("Agentes registrados:")
    for nombre in BuzonGlobal.listar():
        print(f"  - {nombre}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="eventide",
        description="Eventide — organizador inteligente de eventos",
    )
    parser.add_argument(
        "--version", action="version", version="eventide 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve
    p_serve = subparsers.add_parser("serve", help="Arranca la API + agentes")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8502)
    p_serve.add_argument("--debug", action="store_true")
    p_serve.add_argument(
        "--eventos", type=int, default=200,
        help="Nº de eventos sintéticos si no hay embeddings en disco",
    )
    p_serve.set_defaults(func=_cmd_serve)

    # version
    p_version = subparsers.add_parser("version", help="Muestra la versión")
    p_version.set_defaults(func=_cmd_version)

    # agents
    p_agents = subparsers.add_parser("agents", help="Lista agentes registrados")
    p_agents.set_defaults(func=_cmd_agents)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())