"""Tests para el módulo de embeddings."""

import numpy as np
import pytest

from eventide.core.embedding import (
    EventEmbedder,
    _event_in_range,
    _parse_iso,
    load_events_from_folder,
)
from eventide.core.simulation import generar_eventos


# === Fixtures ===

@pytest.fixture(scope="module")
def embedder():
    """Crea un embedder compartido para todos los tests del módulo."""
    EventEmbedder.reset()
    return EventEmbedder()


@pytest.fixture(scope="module")
def small_events():
    """20 eventos sintéticos reproducibles."""
    return generar_eventos(n=20, seed=42)


@pytest.fixture(scope="module")
def embedded(embedder, small_events):
    """Embedder con embeddings + índice ya construidos."""
    embedder.generate_embeddings(small_events)
    embedder.build_index(index_type="flat")
    return embedder


# === Singleton ===

def test_embedder_is_singleton(embedder):
    a = EventEmbedder()
    b = EventEmbedder()
    assert a is b


def test_reset_creates_new_instance():
    EventEmbedder.reset()
    a = EventEmbedder()
    EventEmbedder.reset()
    b = EventEmbedder()
    assert a is not b
    # Restaurar para el resto de tests
    EventEmbedder.reset()


# === build_event_text ===

def test_build_event_text_contains_title(embedder):
    ev = generar_eventos(n=1, seed=1)[0]
    text = embedder.build_event_text(ev)
    assert "Título:" in text
    assert ev["basic_info"]["title"] in text


def test_build_event_text_contains_city(embedder):
    ev = generar_eventos(n=1, seed=1)[0]
    text = embedder.build_event_text(ev)
    assert "Ciudad:" in text
    assert ev["spatial_info"]["area"]["city"] in text


# === Embeddings ===

def test_generate_embeddings_shape(embedder, small_events):
    emb = embedder.generate_embeddings(small_events)
    assert emb.shape == (20, 768)
    assert emb.dtype == np.float32


def test_generate_embeddings_normalized(embedder, small_events):
    emb = embedder.generate_embeddings(small_events)
    norms = np.linalg.norm(emb, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_generate_embeddings_empty_raises(embedder):
    with pytest.raises(ValueError):
        embedder.generate_embeddings([])


# === Index ===

def test_build_index(embedded):
    assert embedded.index is not None
    assert embedded.index.ntotal == 20


# === Shards ===

def test_build_shards(embedded):
    shards = embedded.build_shards()
    assert len(shards) >= 1
    # Cada shard debe tener (index, events)
    for city, (idx, evs) in shards.items():
        assert isinstance(city, str)
        assert idx.ntotal == len(evs)


# === Search ===

def test_search_returns_results(embedded):
    results, scores = embedded.search("concierto", k=5)
    assert len(results) <= 5
    assert all("score" in r for r in results)
    assert all(isinstance(s, float) for s in scores)


def test_search_scores_sorted_desc(embedded):
    results, _ = embedded.search("música", k=10)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_with_shard(embedded):
    # Buscar en un shard específico
    city = list(embedded.shards.keys())[0]
    results, _ = embedded.search("evento", k=5, shard_key=city)
    for r in results:
        assert r["spatial_info"]["area"]["city"] == city


# === Filtered search ===

def test_filtered_search_by_city(embedded):
    city = list(embedded.shards.keys())[0]
    results, _ = embedded.filtered_search("evento", city=city, k=10)
    for r in results:
        assert r["spatial_info"]["area"]["city"] == city


def test_filtered_search_by_category(embedded):
    results, _ = embedded.filtered_search("evento", category="concerts", k=10)
    for r in results:
        cats = r["classification"]
        assert (
            "concerts" in (cats.get("primary_category") or "").lower()
            or any("concerts" in c.lower() for c in cats.get("categories", []))
        )


# === Save / Load ===

def test_save_and_load(embedded, tmp_path):
    embedded.save(tmp_path)
    assert (tmp_path / "eventos.index").exists()
    assert (tmp_path / "eventos_metadata.pkl").exists()
    assert (tmp_path / "eventos_embeddings.npy").exists()

    # Cargar en una instancia nueva
    EventEmbedder.reset()
    loaded = EventEmbedder.load(tmp_path)
    assert loaded.num_events == 20
    assert loaded.index.ntotal == 20
    assert loaded.embeddings.shape == (20, 768)

    # Restaurar
    EventEmbedder.reset()


# === Helpers ===

def test_parse_iso_valid():
    dt = _parse_iso("2025-06-15T21:00:00Z")
    assert dt is not None
    assert dt.year == 2025


def test_parse_iso_invalid():
    assert _parse_iso("no es fecha") is None


def test_event_in_range():
    ev = {"temporal_info": {"start": "2025-06-15T21:00:00Z"}}
    from datetime import datetime, timezone
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, tzinfo=timezone.utc)
    assert _event_in_range(ev, start, end) is True

    end_before = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert _event_in_range(ev, None, end_before) is False


# === load_events_from_folder ===

def test_load_events_empty_folder(tmp_path):
    events = load_events_from_folder(tmp_path)
    assert events == []