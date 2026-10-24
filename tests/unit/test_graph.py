"""Tests para el grafo de conocimiento."""

import pytest

from eventide.core.embedding import EventEmbedder
from eventide.core.knowledge_graph import (
    FESTIVIDADES,
    KnowledgeGraph,
    construir_grafo,
)
from eventide.core.simulation import generar_eventos


# === Fixtures ===

@pytest.fixture(scope="module")
def small_events():
    """30 eventos sintéticos reproducibles."""
    return generar_eventos(n=30, seed=42)


@pytest.fixture(scope="module")
def kg_simple(small_events):
    """Grafo sin similitud (más rápido)."""
    kg = KnowledgeGraph()
    kg.build(small_events, embedder=None)
    return kg


# === Construcción ===

def test_build_creates_graph(kg_simple):
    assert kg_simple.num_nodes > 0
    assert kg_simple.num_edges > 0


def test_num_eventos_nodos(kg_simple, small_events):
    # Cada evento debe ser un nodo
    eventos_nodos = [
        n for n, d in kg_simple.graph.nodes(data=True)
        if d.get("tipo") == "evento"
    ]
    assert len(eventos_nodos) == len(small_events)


def test_ciudades_presentes(kg_simple):
    ciudades = [
        n for n, d in kg_simple.graph.nodes(data=True)
        if d.get("tipo") == "ciudad"
    ]
    assert len(ciudades) >= 1


def test_categorias_presentes(kg_simple):
    cats = [
        n for n, d in kg_simple.graph.nodes(data=True)
        if d.get("tipo") == "categoria"
    ]
    assert len(cats) >= 1


def test_aristas_tipadas(kg_simple):
    tipos_esperados = {"ocurre_en", "es_de_categoria", "tiene_artista"}
    tipos_presentes = {d.get("tipo") for _, _, d in kg_simple.graph.edges(data=True)}
    # Al menos uno de los tipos esperados debe estar
    assert tipos_esperados & tipos_presentes


# === PageRank ===

def test_pagerank_events(kg_simple):
    pr = kg_simple.pagerank_events()
    assert isinstance(pr, dict)
    assert len(pr) > 0
    # Todos los scores positivos
    assert all(v > 0 for v in pr.values())


def test_top_eventos_por_pagerank(kg_simple):
    top = kg_simple.top_eventos_por_pagerank(k=5)
    assert len(top) <= 5
    # Ordenado descendente
    scores = [s for _, s in top]
    assert scores == sorted(scores, reverse=True)


# === Enriquecimiento ===

def test_enriquecer_events(kg_simple, small_events):
    candidatos = small_events[:10]
    enriquecidos = kg_simple.enriquecer(candidatos, "Madrid", k=5)
    assert len(enriquecidos) <= 5
    # Cada elemento es tupla (evento, score)
    for ev, score in enriquecidos:
        assert isinstance(ev, dict)
        assert isinstance(score, (int, float))


def test_enriquecer_ordenado_por_score(kg_simple, small_events):
    candidatos = small_events[:15]
    enriquecidos = kg_simple.enriquecer(candidatos, "concierto", k=15)
    scores = [s for _, s in enriquecidos]
    assert scores == sorted(scores, reverse=True)


# === Persistencia ===

def test_save_and_load(kg_simple, tmp_path):
    path = tmp_path / "grafo.graphml"
    kg_simple.save(path)
    assert path.exists()

    kg2 = KnowledgeGraph.load(path)
    assert kg2.num_nodes == kg_simple.num_nodes
    assert kg2.num_edges == kg_simple.num_edges


def test_load_nonexistent(tmp_path):
    with pytest.raises(FileNotFoundError):
        KnowledgeGraph.load(tmp_path / "noexiste.graphml")


# === Estadísticas ===

def test_estadisticas(kg_simple):
    stats = kg_simple.estadisticas()
    assert "num_nodos" in stats
    assert "num_aristas" in stats
    assert "nodos_por_tipo" in stats
    assert "aristas_por_tipo" in stats
    assert stats["num_nodos"] == kg_simple.num_nodes


# === API de conveniencia ===

def test_construir_grafo(small_events):
    kg = construir_grafo(small_events, embedder=None)
    assert isinstance(kg, KnowledgeGraph)
    assert kg.num_nodes > 0
    
def test_categoria_no_es_pisada_por_subcategoria(kg_simple):
    """
    Regresión: si primary_category == categories[0], el nodo debe
    seguir siendo 'categoria', no 'subcategoria'.
    """
    eventos = [
        {
            "id": "evt_test_1",
            "basic_info": {"title": "Test"},
            "classification": {
                "primary_category": "concerts",
                "categories": ["concerts"],  # ← mismo valor
            },
            "spatial_info": {"area": {"city": "Madrid"}},
            "temporal_info": {"start": "2025-06-15T21:00:00+00:00"},
        }
    ]
    kg = KnowledgeGraph()
    kg.build(eventos, embedder=None)

    assert kg.graph.has_node("concerts")
    assert kg.graph.nodes["concerts"]["tipo"] == "categoria"


def test_deduplicacion_nodos_taxonomicos(kg_simple):
    """
    Si un artista coincide con una categoría (raro pero posible),
    el nodo solo debe existir una vez.
    """
    eventos = [
        {
            "id": "evt_test_2",
            "basic_info": {"title": "Test"},
            "classification": {"primary_category": "arts"},
            "spatial_info": {"area": {"city": "Madrid"}},
            "temporal_info": {"start": "2025-06-15T21:00:00+00:00"},
            "participants": {
                "performers": [{"name": "arts"}]  # colisión
            },
        }
    ]
    kg = KnowledgeGraph()
    kg.build(eventos, embedder=None)

    # Solo debe existir una vez, con el tipo del primero añadido (categoria)
    assert kg.graph.number_of_nodes() >= 1
    assert kg.graph.nodes["arts"]["tipo"] == "categoria"