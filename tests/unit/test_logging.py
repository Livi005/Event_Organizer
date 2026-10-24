"""Tests para el módulo de logging."""

from eventide.logging_config import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert logger is not None


def test_logger_does_not_crash(capsys):
    """Verificar que el logger no lanza excepciones."""
    logger = get_logger("test_module")
    logger.info("Mensaje de prueba")
    logger.warning("Advertencia")
    logger.error("Error simulado")
    # Si llegamos aquí sin excepción, el test pasa