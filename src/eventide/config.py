"""
Configuración central de Eventide.

Carga variables de entorno desde `.env`, valida tipos con Pydantic,
y expone un objeto `settings` de acceso global.

Uso:
    from eventide.config import settings
    print(settings.api_port)
    settings.ensure_directories()
"""

from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# === Raíz del proyecto ===
# config.py está en src/eventide/config.py → subimos 3 niveles hasta la raíz
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Configuración validada del sistema Eventide.

    Todas las variables se pueden sobrescribir desde `.env` (mismo nombre,
    sin prefijo) o desde variables de entorno del sistema operativo.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==========================================
    # ENTORNO
    # ==========================================
    env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        description="Entorno de ejecución actual.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Nivel mínimo de logging.",
    )

    # ==========================================
    # RUTAS
    # ==========================================
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    raw_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw")
    processed_dir: Path = Field(default=PROJECT_ROOT / "data" / "processed")
    eval_dir: Path = Field(default=PROJECT_ROOT / "data" / "eval")
    synthetic_dir: Path = Field(default=PROJECT_ROOT / "data" / "synthetic")
    embeddings_dir: Path = Field(default=PROJECT_ROOT / "embedding_data")
    graph_dir: Path = Field(default=PROJECT_ROOT / "grafo")
    logs_dir: Path = Field(default=PROJECT_ROOT / "logs")

    # ==========================================
    # APIs EXTERNAS DE EVENTOS
    # ==========================================
    predicthq_api_key: SecretStr = Field(default=SecretStr(""))
    seatgeek_client_id: SecretStr = Field(default=SecretStr(""))
    ticketmaster_api_key: SecretStr = Field(default=SecretStr(""))

    # ==========================================
    # LLM
    # ==========================================
    gemini_api_key: SecretStr = Field(default=SecretStr(""))
    gemini_model: str = Field(default="gemini-1.5-flash")

    # ==========================================
    # MODELO DE EMBEDDINGS
    # ==========================================
    model_name: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        description="Modelo de SentenceTransformers para generar embeddings.",
    )
    embedding_dim: int = Field(default=768, description="Dimensión de los embeddings.")

    # ==========================================
    # API REST
    # ==========================================
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8502)
    api_timeout_seconds: int = Field(default=60)

    # ==========================================
    # UI
    # ==========================================
    ui_port: int = Field(default=8501)

    # ==========================================
    # SCRAPING
    # ==========================================
    max_events_per_source: int = Field(default=2000)
    scraping_delay_seconds: float = Field(default=0.5)
    scraping_max_workers: int = Field(default=5)

    # ==========================================
    # OPTIMIZACIÓN (Simulated Annealing)
    # ==========================================
    default_agenda_size: int = Field(default=5)
    sa_max_iterations: int = Field(default=300)
    sa_initial_temperature: float = Field(default=100.0)
    sa_final_temperature: float = Field(default=0.1)

    # ==========================================
    # FALLBACK
    # ==========================================
    fallback_threshold: int = Field(
        default=3,
        description="Nº mínimo de resultados antes de disparar fallback.",
    )

    # ==========================================
    # FEATURE FLAGS
    # ==========================================
    use_knowledge_graph: bool = Field(default=True)
    use_fallback: bool = Field(default=True)
    use_llm_validator: bool = Field(default=True)

    # ==========================================
    # MÉTODOS DE UTILIDAD
    # ==========================================
    def ensure_directories(self) -> None:
        """Crea todas las carpetas necesarias si no existen."""
        for directory in (
            self.data_dir,
            self.raw_dir,
            self.processed_dir,
            self.eval_dir,
            self.synthetic_dir,
            self.embeddings_dir,
            self.graph_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def is_development(self) -> bool:
        """True si estamos en entorno de desarrollo."""
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        """True si estamos en entorno de producción."""
        return self.env == "production"

    @property
    def has_event_api_keys(self) -> bool:
        """True si al menos una API de eventos tiene key configurada."""
        return any(
            [
                self.predicthq_api_key.get_secret_value(),
                self.seatgeek_client_id.get_secret_value(),
                self.ticketmaster_api_key.get_secret_value(),
            ]
        )

    @property
    def has_llm_key(self) -> bool:
        """True si el LLM está configurado."""
        return bool(self.gemini_api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Devuelve la instancia única de configuración (cacheada).

    Al ser un singleton, todos los módulos comparten la misma instancia
    y los cambios en `.env` requieren reiniciar el proceso.
    """
    return Settings()


# ==========================================
# ALIAS DE CONVENIENCIA
# ==========================================
settings = get_settings()


# ==========================================
# EJECUCIÓN DIRECTA (útil para debug)
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("Eventide — Configuración cargada")
    print("=" * 60)
    print(f"Entorno:        {settings.env}")
    print(f"Log level:      {settings.log_level}")
    print(f"Raíz proyecto:  {PROJECT_ROOT}")
    print(f"Data dir:       {settings.data_dir}")
    print(f"Embeddings dir: {settings.embeddings_dir}")
    print(f"API:            {settings.api_host}:{settings.api_port}")
    print(f"Modelo:         {settings.model_name}")
    print(f"API keys:       {'OK' if settings.has_event_api_keys else 'FALTAN'}")
    print(f"LLM key:        {'OK' if settings.has_llm_key else 'FALTA'}")
    print("=" * 60)