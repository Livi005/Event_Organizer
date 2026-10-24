"""
Agente de optimización de agendas.

Envuelve `optimizar_agenda` (SA / HC / Random) en un agente con mensajes.

Mensajes que acepta:
    tipo="optimizar": payload = {
        "pool": list[dict] (requerido),
        "preferencias": dict (requerido),
        "cantidad": int = 5,
        "algoritmo": "sa" | "hc" | "random" = "sa",
        "seed": int | None,
        "scores_grafo": dict | None,
        "respuesta_a": str
    }

Mensajes que emite:
    tipo="agenda_optimizada": payload = {
        "agenda": list[dict],
        "score": float,
        "trace": list[float],
        "algoritmo": str,
        "cantidad": int
    }
"""

from __future__ import annotations

import time
from typing import Any

from eventide.agents.base import AgenteBase, Mensaje
from eventide.core.optimizer import ALGORITMOS, optimizar_agenda


class AgenteOptimizador(AgenteBase):
    """
    Agente que genera agendas optimizadas.

    No mantiene estado entre llamadas: cada petición es independiente.
    Acepta cualquier combinación de pool + preferencias.
    """

    def __init__(self, nombre: str = "optimizador") -> None:
        super().__init__(nombre)
        self.optimizaciones_realizadas = 0
        self.tiempo_total_ms = 0.0

    # ---------------------------------------------------------
    # MANEJO DE MENSAJES
    # ---------------------------------------------------------

    def manejar_mensaje(self, msg: Mensaje) -> None:
        if msg.tipo == "optimizar":
            self._handle_optimizar(msg)
        elif msg.tipo == "stats":
            self._handle_stats(msg)
        elif msg.tipo == "algoritmos_disponibles":
            self._responder(msg, "algoritmos_disponibles", {
                "algoritmos": list(ALGORITMOS.keys()),
            })
        else:
            self.logger.debug(f"Tipo no soportado: {msg.tipo}")

    # ---------------------------------------------------------
    # HANDLERS
    # ---------------------------------------------------------

    def _handle_optimizar(self, msg: Mensaje) -> None:
        payload = msg.payload

        pool = payload.get("pool") or []
        preferencias = payload.get("preferencias") or {}
        cantidad = int(payload.get("cantidad", 5))
        algoritmo = payload.get("algoritmo", "sa")
        seed = payload.get("seed")
        scores_grafo = payload.get("scores_grafo")

        # Validación
        if not pool:
            self._responder_error(msg, "pool vacío")
            return
        if not preferencias:
            self._responder_error(msg, "preferencias vacías")
            return
        if algoritmo not in ALGORITMOS:
            self._responder_error(
                msg,
                f"algoritmo desconocido: {algoritmo}. "
                f"Válidos: {list(ALGORITMOS.keys())}",
            )
            return
        if len(pool) < cantidad:
            self._responder_error(
                msg,
                f"pool insuficiente: {len(pool)} eventos para cantidad={cantidad}",
            )
            return

        # Ejecutar
        t0 = time.perf_counter()
        try:
            agenda, score, trace = optimizar_agenda(
                pool=pool,
                preferencias=preferencias,
                cantidad=cantidad,
                algoritmo=algoritmo,
                seed=seed,
                scores_grafo=scores_grafo,
            )
        except Exception as e:
            self.logger.error(f"Error en optimización: {e}", exc_info=True)
            self._responder_error(msg, str(e))
            return

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.optimizaciones_realizadas += 1
        self.tiempo_total_ms += elapsed_ms

        self.logger.info(
            f"Agenda generada: algoritmo={algoritmo}, "
            f"score={score:.2f}, tiempo={elapsed_ms:.1f}ms"
        )

        self._responder(msg, "agenda_optimizada", {
            "agenda": agenda,
            "score": score,
            "trace": trace,
            "algoritmo": algoritmo,
            "cantidad": cantidad,
            "tiempo_ms": round(elapsed_ms, 2),
        })

    def _handle_stats(self, msg: Mensaje) -> None:
        media_ms = (
            self.tiempo_total_ms / self.optimizaciones_realizadas
            if self.optimizaciones_realizadas > 0
            else 0.0
        )
        self._responder(msg, "stats_optimizador", {
            "optimizaciones_realizadas": self.optimizaciones_realizadas,
            "tiempo_medio_ms": round(media_ms, 2),
            "algoritmos_disponibles": list(ALGORITMOS.keys()),
        })

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def _responder(self, msg: Mensaje, tipo: str, payload: dict[str, Any]) -> None:
        destino = msg.payload.get("respuesta_a")
        if destino:
            self.enviar(destino, tipo, payload)
        else:
            self.logger.warning(f"Sin 'respuesta_a', no puedo responder {tipo}")

    def _responder_error(self, msg: Mensaje, error: str) -> None:
        self.logger.warning(f"Error en optimización: {error}")
        self._responder(msg, "agenda_optimizada", {
            "agenda": [],
            "score": 0.0,
            "trace": [],
            "error": error,
        })