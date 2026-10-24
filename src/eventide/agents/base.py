"""
Clase base para todos los agentes de Eventide.

Un agente:
- Tiene un nombre único y una bandeja de entrada (Queue thread-safe).
- Se ejecuta en su propio hilo (daemon).
- Se comunica con otros agentes mediante mensajes tipados.
- Puede enviar mensajes a otros agentes por nombre.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any

from eventide.logging_config import get_logger


# =============================================================
# MENSAJE ENTRE AGENTES
# =============================================================

@dataclass
class Mensaje:
    """Mensaje que circula entre agentes."""

    emisor: str
    receptor: str
    tipo: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __repr__(self) -> str:
        return (
            f"Mensaje({self.emisor}→{self.receptor}, "
            f"tipo={self.tipo}, keys={list(self.payload.keys())})"
        )


# =============================================================
# REGISTRO GLOBAL DE BANDEJAS
# =============================================================

class BuzonGlobal:
    """Registro thread-safe de bandejas por agente."""

    _bandejas: dict[str, Queue] = {}
    _lock = threading.Lock()

    @classmethod
    def registrar(cls, nombre: str, bandeja: Queue) -> None:
        with cls._lock:
            cls._bandejas[nombre] = bandeja

    @classmethod
    def obtener(cls, nombre: str) -> Queue | None:
        with cls._lock:
            return cls._bandejas.get(nombre)

    @classmethod
    def listar(cls) -> list[str]:
        with cls._lock:
            return sorted(cls._bandejas.keys())

    @classmethod
    def limpiar(cls) -> None:
        with cls._lock:
            cls._bandejas.clear()


# =============================================================
# AGENTE BASE
# =============================================================

class AgenteBase(ABC):
    """
    Agente autónomo que corre en su propio hilo.

    Ciclo de vida:
        - __init__: registra su bandeja en el BuzonGlobal.
        - start(): arranca el hilo (daemon).
        - _loop(): consume mensajes hasta que se pida parar.
        - stop(): envía señal de parada y espera al hilo.
    """

    def __init__(self, nombre: str, poll_timeout: float = 0.5) -> None:
        self.nombre = nombre
        self.bandeja: Queue = Queue()
        self.poll_timeout = poll_timeout
        self.logger = get_logger(f"agents.{nombre}")

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._mensajes_procesados = 0
        self._inicio = datetime.now(timezone.utc)

        BuzonGlobal.registrar(nombre, self.bandeja)
        self.logger.debug(f"Agente '{nombre}' registrado")

    # ---------------------------------------------------------
    # CICLO DE VIDA
    # ---------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self.logger.warning(f"Agente '{self.nombre}' ya está corriendo")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"agente-{self.nombre}",
            daemon=True,
        )
        self._thread.start()
        self.logger.info(f"🚀 Agente '{self.nombre}' arrancado")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                self.logger.warning(
                    f"Agente '{self.nombre}' no se detuvo en {timeout}s"
                )
            else:
                self.logger.info(f"🛑 Agente '{self.nombre}' detenido")

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> dict[str, Any]:
        uptime = (datetime.now(timezone.utc) - self._inicio).total_seconds()
        return {
            "nombre": self.nombre,
            "running": self.running,
            "mensajes_procesados": self._mensajes_procesados,
            "uptime_seconds": round(uptime, 2),
            "cola_size": self.bandeja.qsize(),
        }

    # ---------------------------------------------------------
    # COMUNICACIÓN
    # ---------------------------------------------------------

    def enviar(
        self,
        receptor: str,
        tipo: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        bandeja_destino = BuzonGlobal.obtener(receptor)
        if bandeja_destino is None:
            self.logger.warning(
                f"Receptor '{receptor}' no encontrado. "
                f"Disponibles: {BuzonGlobal.listar()}"
            )
            return False

        msg = Mensaje(
            emisor=self.nombre,
            receptor=receptor,
            tipo=tipo,
            payload=payload or {},
        )
        bandeja_destino.put(msg)
        self.logger.debug(f"→ {receptor}: {tipo}")
        return True

    def recibir(self, timeout: float | None = None) -> Mensaje | None:
        try:
            return self.bandeja.get(timeout=timeout or self.poll_timeout)
        except Empty:
            return None

    # ---------------------------------------------------------
    # LOOP PRINCIPAL
    # ---------------------------------------------------------

    def _loop(self) -> None:
        self.logger.debug(f"Agente '{self.nombre}' entrando en loop")

        try:
            self.setup()
        except Exception as e:
            self.logger.error(f"Error en setup(): {e}", exc_info=True)
            return

        while not self._stop_event.is_set():
            msg = self.recibir(timeout=self.poll_timeout)
            if msg is None:
                continue

            if msg.receptor != self.nombre:
                self.bandeja.put(msg)
                time.sleep(0.01)
                continue

            try:
                self.manejar_mensaje(msg)
                self._mensajes_procesados += 1
            except Exception as e:
                self.logger.error(
                    f"Error manejando {msg.tipo}: {e}",
                    exc_info=True,
                )
                self.on_error(msg, e)

        try:
            self.teardown()
        except Exception as e:
            self.logger.error(f"Error en teardown(): {e}")

        self.logger.debug(f"Agente '{self.nombre}' saliendo del loop")

    # ---------------------------------------------------------
    # HOOKS
    # ---------------------------------------------------------

    def setup(self) -> None:
        """Hook de inicialización."""

    def teardown(self) -> None:
        """Hook de limpieza."""

    def on_error(self, msg: Mensaje, error: Exception) -> None:
        """Hook de manejo de errores."""

    # ---------------------------------------------------------
    # CONTRATO
    # ---------------------------------------------------------

    @abstractmethod
    def manejar_mensaje(self, msg: Mensaje) -> None:
        """Procesa un mensaje dirigido a este agente."""
        ...