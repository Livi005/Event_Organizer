"""Tests para el módulo de configuración."""

from pathlib import Path

from eventide.config import Settings, get_settings


def test_settings_loads_defaults():
    """Los valores por defecto deben cargarse correctamente."""
    s = Settings()
    assert s.env in ("development", "staging", "production", "test")
    assert s.api_port == 8502
    assert s.default_agenda_size == 5
    assert s.use_knowledge_graph is True


def test_settings_paths_are_absolute():
    """Todas las rutas deben ser absolutas."""
    s = Settings()
    assert s.data_dir.is_absolute()
    assert s.raw_dir.is_absolute()
    assert s.embeddings_dir.is_absolute()


def test_settings_is_singleton():
    """get_settings() debe devolver siempre la misma instancia."""
    a = get_settings()
    b = get_settings()
    assert a is b


def test_ensure_directories_creates_folders(tmp_path, monkeypatch):
    """ensure_directories() debe crear las carpetas si no existen."""
    s = Settings(
        data_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        processed_dir=tmp_path / "data" / "processed",
        eval_dir=tmp_path / "data" / "eval",
        synthetic_dir=tmp_path / "data" / "synthetic",
        embeddings_dir=tmp_path / "emb",
        graph_dir=tmp_path / "graph",
        logs_dir=tmp_path / "logs",
    )
    s.ensure_directories()
    assert (tmp_path / "data" / "raw").exists()
    assert (tmp_path / "logs").exists()