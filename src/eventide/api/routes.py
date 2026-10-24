"""
Rutas REST de la API de Eventide.

Endpoints (todos bajo /api/v1):

  POST /buscar
    body: { query, ciudad?, categoria?, fecha_inicio?, fecha_fin?, k? }
    response: { resultados, total, query, query_corregida, sugerencias }

  POST /agenda
    body: { pool, preferencias, cantidad?, algoritmo?, seed? }
    response: { agenda, score, trace, algoritmo }

  POST /narrar
    body: { agenda, preferencias, query_original? }
    response: { texto, fuente, tiempo_ms }

  GET /agentes
    response: { agentes }

  GET /ciudades
    response: { ciudades }

  GET /categorias
    response: { categorias }
"""

from __future__ import annotations

import time
import uuid
from queue import Empty, Queue
from typing import Any

from flask import Blueprint, jsonify, request

from eventide.agents.base import BuzonGlobal, Mensaje
from eventide.config import settings
from eventide.logging_config import get_logger

logger = get_logger(__name__)

api_bp = Blueprint("api", __name__)


# =============================================================
# UTILIDADES INTERNAS
# =============================================================

def _crear_buzon_respuesta() -> tuple[str, Queue]:
    """Crea una bandeja temporal para recibir una respuesta."""
    key = f"resp_{uuid.uuid4().hex[:12]}"
    q: Queue = Queue()
    BuzonGlobal.registrar(key, q)
    return key, q


def _limpiar_buzon(key: str) -> None:
    """Elimina la bandeja temporal (evita leaks)."""
    with BuzonGlobal._lock:
        BuzonGlobal._bandejas.pop(key, None)


def _enviar_y_esperar(
    agente_destino: str,
    tipo: str,
    payload: dict[str, Any],
    tipo_respuesta_esperada: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    Envia un mensaje a un agente y espera su respuesta por una cola temporal.

    Returns:
        El payload de la respuesta.

    Raises:
        TimeoutError: si no hay respuesta en `timeout` segundos.
        RuntimeError: si el agente destino no existe.
    """
    bandeja_destino = BuzonGlobal.obtener(agente_destino)
    if bandeja_destino is None:
        raise RuntimeError(f"Agente '{agente_destino}' no registrado")

    key, cola = _crear_buzon_respuesta()
    payload = {**payload, "respuesta_a": key}

    try:
        bandeja_destino.put(
            Mensaje(
                emisor="api",
                receptor=agente_destino,
                tipo=tipo,
                payload=payload,
            )
        )

        inicio = time.time()
        while time.time() - inicio < timeout:
            try:
                respuesta: Mensaje = cola.get(timeout=1.0)
                if respuesta.tipo == tipo_respuesta_esperada:
                    return respuesta.payload
            except Empty:
                continue

        raise TimeoutError(
            f"Timeout esperando '{tipo_respuesta_esperada}' de '{agente_destino}'"
        )
    finally:
        _limpiar_buzon(key)


def _limpiar_evento(ev: dict[str, Any]) -> dict[str, Any]:
    """Serializa un evento para JSON (quita campos problematicos)."""
    from datetime import date, datetime
    from copy import deepcopy

    nuevo = deepcopy(ev)
    for k in list(nuevo.keys()):
        if k.startswith("__"):
            del nuevo[k]
        elif isinstance(nuevo[k], (datetime, date)):
            nuevo[k] = str(nuevo[k])
    return nuevo


# =============================================================
# ENDPOINTS
# =============================================================

@api_bp.route("/buscar", methods=["POST"])
def buscar():
    """Busqueda semantica de eventos con correccion ortografica."""
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "query vacia"}), 400

    try:
        resultado = _enviar_y_esperar(
            agente_destino="buscador",
            tipo="buscar",
            payload={
                "query": query,
                "ciudad": data.get("ciudad"),
                "categoria": data.get("categoria"),
                "fecha_inicio": data.get("fecha_inicio"),
                "fecha_fin": data.get("fecha_fin"),
                "k": int(data.get("k", 60)),
            },
            tipo_respuesta_esperada="resultados_busqueda",
            timeout=30.0,
        )

        limpios = [_limpiar_evento(r) for r in resultado.get("resultados", [])]
        return jsonify({
            "status": "ok",
            "query": resultado.get("query"),
            "query_corregida": resultado.get("query_corregida"),
            "sugerencias": resultado.get("sugerencias", []),
            "total": len(limpios),
            "resultados": limpios,
        }), 200

    except TimeoutError as e:
        logger.error(f"Timeout en /buscar: {e}")
        return jsonify({"error": "timeout del buscador"}), 504
    except Exception as e:
        logger.error(f"Error en /buscar: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/agenda", methods=["POST"])
def agenda():
    """Genera una agenda optimizada."""
    data = request.get_json(silent=True) or {}

    pool = data.get("pool") or []
    preferencias = data.get("preferencias") or {}

    if not pool:
        return jsonify({"error": "pool vacio"}), 400
    if not preferencias:
        return jsonify({"error": "preferencias vacias"}), 400

    try:
        resultado = _enviar_y_esperar(
            agente_destino="optimizador",
            tipo="optimizar",
            payload={
                "pool": pool,
                "preferencias": preferencias,
                "cantidad": int(data.get("cantidad", settings.default_agenda_size)),
                "algoritmo": data.get("algoritmo", "sa"),
                "seed": data.get("seed"),
                "scores_grafo": data.get("scores_grafo"),
            },
            tipo_respuesta_esperada="agenda_optimizada",
            timeout=60.0,
        )

        if "error" in resultado:
            return jsonify({"error": resultado["error"]}), 400

        agenda_limpia = [_limpiar_evento(ev) for ev in resultado.get("agenda", [])]
        return jsonify({
            "status": "ok",
            "agenda": agenda_limpia,
            "score": resultado.get("score", 0.0),
            "trace": resultado.get("trace", []),
            "algoritmo": resultado.get("algoritmo"),
            "tiempo_ms": resultado.get("tiempo_ms"),
        }), 200

    except TimeoutError as e:
        logger.error(f"Timeout en /agenda: {e}")
        return jsonify({"error": "timeout del optimizador"}), 504
    except Exception as e:
        logger.error(f"Error en /agenda: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/narrar", methods=["POST"])
def narrar():
    """Narra una agenda en lenguaje natural."""
    data = request.get_json(silent=True) or {}

    agenda = data.get("agenda") or []
    preferencias = data.get("preferencias") or {}

    if not agenda:
        return jsonify({"error": "agenda vacia"}), 400

    try:
        resultado = _enviar_y_esperar(
            agente_destino="narrador",
            tipo="narrar",
            payload={
                "agenda": agenda,
                "preferencias": preferencias,
                "scores_grafo": data.get("scores_grafo"),
                "query_original": data.get("query_original"),
                "alternativas_descartadas": data.get("alternativas_descartadas", []),
            },
            tipo_respuesta_esperada="narracion_lista",
            timeout=30.0,
        )

        return jsonify({
            "status": "ok",
            "texto": resultado.get("texto", ""),
            "fuente": resultado.get("fuente"),
            "tiempo_ms": resultado.get("tiempo_ms"),
            "cache_hit": resultado.get("cache_hit", False),
            "analisis": resultado.get("analisis", {}),
        }), 200

    except TimeoutError as e:
        logger.error(f"Timeout en /narrar: {e}")
        return jsonify({"error": "timeout del narrador"}), 504
    except Exception as e:
        logger.error(f"Error en /narrar: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/agentes", methods=["GET"])
def listar_agentes():
    """Lista los agentes registrados."""
    return jsonify({
        "status": "ok",
        "agentes": BuzonGlobal.listar(),
    }), 200


@api_bp.route("/ciudades", methods=["GET"])
def listar_ciudades():
    """Lista las ciudades disponibles (extraidas del indice de embeddings)."""
    try:
        from eventide.core.embedding import EventEmbedder

        try:
            embedder = EventEmbedder.get_instance()
        except RuntimeError:
            return jsonify({
                "status": "ok",
                "ciudades": [],
                "aviso": "embedder no inicializado",
            }), 200

        ciudades = set()
        for ev in embedder.events:
            city = ev.get("spatial_info", {}).get("area", {}).get("city")
            if city:
                ciudades.add(city)
        return jsonify({"status": "ok", "ciudades": sorted(ciudades)}), 200
    except Exception as e:
        logger.error(f"Error en /ciudades: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/categorias", methods=["GET"])
def listar_categorias():
    """Lista las categorias disponibles."""
    try:
        from eventide.core.embedding import EventEmbedder

        try:
            embedder = EventEmbedder.get_instance()
        except RuntimeError:
            return jsonify({
                "status": "ok",
                "categorias": [],
                "aviso": "embedder no inicializado",
            }), 200

        categorias = set()
        for ev in embedder.events:
            cat = ev.get("classification", {}).get("primary_category")
            if cat:
                categorias.add(cat)
        return jsonify({"status": "ok", "categorias": sorted(categorias)}), 200
    except Exception as e:
        logger.error(f"Error en /categorias: {e}")
        return jsonify({"error": str(e)}), 500
