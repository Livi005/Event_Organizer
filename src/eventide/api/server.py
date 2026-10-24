"""
Servidor Flask para la API de Eventide.

- Inicializa la app Flask.
- Registra las rutas.
- Expone una función `run()` para arrancar el servidor.
- Expone `crear_app()` para que tests puedan instanciar sin servidor.
"""

from __future__ import annotations

from flask import Flask, jsonify

from eventide.logging_config import get_logger

logger = get_logger(__name__)


def crear_app() -> Flask:
    """Factory: crea e instancia la app Flask con las rutas registradas."""
    app = Flask(__name__)

    # Configuración
    app.config["JSON_SORT_KEYS"] = False

    # Health check
    @app.route("/ping", methods=["GET"])
    def ping():
        return jsonify({"status": "ok", "service": "eventide"}), 200

    @app.route("/health", methods=["GET"])
    def health():
        # Import aquí para evitar circular imports
        from eventide.agents.base import BuzonGlobal

        return jsonify({
            "status": "healthy",
            "agentes_registrados": BuzonGlobal.listar(),
        }), 200

    # Importar y registrar las rutas
    from eventide.api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")

    logger.info("App Flask creada con rutas registradas")
    return app


def run(host: str = "0.0.0.0", port: int = 8502, debug: bool = False) -> None:
    """Arranca el servidor Flask."""
    app = crear_app()
    logger.info(f"🚀 Arrancando API en http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)