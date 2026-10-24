"""
Configuración central de logging para Eventide.

Usa loguru para:
- Consola con colores en desarrollo
- Rotación automática de archivos
- Formato JSON opcional en producción
- Un logger por módulo con contexto
"""

import sys
from pathlib import Path

from loguru import logger

from eventide.config import settings


# === Formato para consola (legible) ===
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[module]}</cyan> | "
    "<level>{message}</level>"
)

# === Formato para archivo (JSON estructurado) ===
FILE_FORMAT = (
    "{{"
    '"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
    '"level": "{level}", '
    '"module": "{extra[module]}", '
    '"function": "{function}", '
    '"line": {line}, '
    '"message": "{message}"'
    "}}"
)


def _configure_logger() -> None:
    """Configura loguru con sinks de consola y archivo."""
    # Eliminar el handler por defecto
    logger.remove()

    # === Sink 1: consola ===
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.is_development,
    )

    # === Sink 2: archivo rotativo ===
    logs_dir = Path(settings.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        logs_dir / "eventide_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="DEBUG",
        rotation="00:00",          # rota cada día
        retention="30 days",        # conserva 30 días
        compression="zip",          # comprime los antiguos
        encoding="utf-8",
        enqueue=True,               # thread-safe (importante con agentes)
        backtrace=True,
        diagnose=False,
    )


def get_logger(module_name: str):
    """
    Devuelve un logger con contexto del módulo.

    Uso:
        logger = get_logger(__name__)
        logger.info("Mensaje")
    """
    return logger.bind(module=module_name)


# Configurar al importar
_configure_logger()