"""
Módulo de grafo de conocimiento neuro-simbólico.

Construye un MultiDiGraph de NetworkX donde:
- Los eventos son nodos centrales.
- Ciudades, categorías, artistas, fechas, festividades son nodos de contexto.
- Las aristas representan relaciones tipadas.
- Eventos similares (coseno > umbral) se conectan con "similar_a".

Permite:
- PageRank sobre eventos (ranking global).
- Razonamiento multi-hop (enriquecer resultados de búsqueda).
- Exportación a GraphML para visualización.

Uso:
    from eventide.core.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.build(eventos)
    ranking = kg.pagerank_events()
    enriquecidos = kg.enriquecer(eventos_query, "concierto rock")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from eventide.config import settings
from eventide.core.embedding import EventEmbedder
from eventide.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================
# CONSTANTES
# =============================================================

# Umbral de similitud coseno para conectar eventos con "similar_a"
SIMILARITY_THRESHOLD: float = 0.88

# Festividades: mes-día (MM-DD)
FESTIVIDADES: dict[str, list[str]] = {
    "navidad": ["12-25", "12-24", "12-31"],
    "ano_nuevo": ["01-01"],
    "reyes": ["01-06"],
    "halloween": ["10-31"],
    "san_valentin": ["02-14"],
    "dia_muertos": ["11-01", "11-02"],
    "ramadan_fin": ["04-21"],
    "viernes_santo": ["04-15", "04-18"],
    "san_juan": ["06-24"],
    "hispanidad": ["10-12"],
}

# Estaciones (por mes)
ESTACIONES: dict[str, list[int]] = {
    "invierno": [12, 1, 2],
    "primavera": [3, 4, 5],
    "verano": [6, 7, 8],
    "otono": [9, 10, 11],
}


# =============================================================
# KNOWLEDGE GRAPH
# =============================================================

class KnowledgeGraph:
    """
    Grafo de conocimiento neuro-simbólico de eventos.

    Atributos:
        graph: MultiDiGraph de NetworkX.
        events: lista de eventos que están en el grafo.
    """

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self.events: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # CONSTRUCCIÓN
    # ---------------------------------------------------------

    def build(
        self,
        events: list[dict[str, Any]],
        embedder: EventEmbedder | None = None,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ) -> nx.MultiDiGraph:
        """
        Construye el grafo completo a partir de una lista de eventos.

        Args:
            events: lista de eventos en formato enriquecido.
            embedder: instancia de EventEmbedder para similitud.
                      Si None, intenta obtener el singleton.
            similarity_threshold: umbral para conectar eventos similares.

        Returns:
            El grafo construido.
        """
        logger.info(f"Construyendo grafo con {len(events)} eventos...")
        self.graph.clear()
        self.events = events

        # Paso 1: añadir nodos y aristas estructurales
        for ev in events:
            self._add_event(ev)

        # Paso 2: añadir aristas de similitud semántica
        try:
            self._add_similarity_edges(events, embedder, similarity_threshold)
        except Exception as e:
            logger.warning(f"No se pudieron añadir aristas de similitud: {e}")

        logger.info(
            f"Grafo construido: {self.graph.number_of_nodes()} nodos, "
            f"{self.graph.number_of_edges()} aristas"
        )
        return self.graph

    def _add_event(self, ev: dict[str, Any]) -> None:
        """Añade un evento y sus relaciones estructurales al grafo."""
        ev_id = self._event_id(ev)
        self.graph.add_node(
            ev_id,
            tipo="evento",
            data=json.dumps(ev, default=str),
        )

        # --- Ciudad ---
        ciudad = ev.get("spatial_info", {}).get("area", {}).get("city")
        if ciudad:
            self._add_taxonomy_node(ciudad, "ciudad")
            self.graph.add_edge(ev_id, ciudad, tipo="ocurre_en")

        # --- País ---
        pais = ev.get("spatial_info", {}).get("area", {}).get("country")
        if pais:
            self._add_taxonomy_node(pais, "pais")
            self.graph.add_edge(ev_id, pais, tipo="ocurre_en")

        # --- Categoría principal ---
        cat_principal = ev.get("classification", {}).get("primary_category")
        if cat_principal:
            self._add_taxonomy_node(cat_principal, "categoria")
            self.graph.add_edge(ev_id, cat_principal, tipo="es_de_categoria")

        # --- Subcategorías (excluyendo la principal) ---
        for sub in ev.get("classification", {}).get("categories", []):
            if sub and sub != cat_principal:  # ← evita colisión
                self._add_taxonomy_node(sub, "subcategoria")
                self.graph.add_edge(ev_id, sub, tipo="es_de_subcategoria")

        # --- Tags ---
        for tag in ev.get("classification", {}).get("tags", []):
            if tag and tag != cat_principal:
                self._add_taxonomy_node(tag, "tag")
                self.graph.add_edge(ev_id, tag, tipo="tiene_tag")

        # --- Artistas / performers ---
        for p in ev.get("participants", {}).get("performers", []):
            nombre = p.get("name")
            if nombre:
                self._add_taxonomy_node(nombre, "artista")
                self.graph.add_edge(ev_id, nombre, tipo="tiene_artista")

        # --- Organizadores ---
        for o in ev.get("participants", {}).get("organizers", []):
            nombre = o.get("name")
            if nombre:
                self._add_taxonomy_node(nombre, "organizador")
                self.graph.add_edge(ev_id, nombre, tipo="organizado_por")

        # --- Venue ---
        venue = ev.get("spatial_info", {}).get("venue", {}).get("name")
        if venue:
            self._add_taxonomy_node(venue, "venue")
            self.graph.add_edge(ev_id, venue, tipo="ocurre_en_venue")

        # --- Fecha, estación, festividad ---
        fecha_str = ev.get("temporal_info", {}).get("start")
        if fecha_str:
            fecha = self._parse_date(fecha_str)
            if fecha:
                fecha_key = fecha.strftime("%Y-%m-%d")
                self._add_taxonomy_node(fecha_key, "fecha")
                self.graph.add_edge(ev_id, fecha_key, tipo="ocurre_en_fecha")

                for estacion, meses in ESTACIONES.items():
                    if fecha.month in meses:
                        self._add_taxonomy_node(estacion, "estacion")
                        self.graph.add_edge(ev_id, estacion, tipo="ocurre_en_estacion")
                        break

                mm_dd = fecha.strftime("%m-%d")
                for festividad, fechas in FESTIVIDADES.items():
                    if mm_dd in fechas:
                        self._add_taxonomy_node(festividad, "festividad")
                        self.graph.add_edge(ev_id, festividad, tipo="ocurre_en_festividad")

    def _add_taxonomy_node(self, nombre: str, tipo: str) -> None:
        """
        Añade o refuerza un nodo taxonómico.

        Si el nodo ya existe con OTRO tipo, NO lo pisa. Esto evita
        que una categoría se convierta en subcategoría (o viceversa)
        por colisión de nombres.

        La regla de prioridad es: el tipo ya asignado gana.
        """
        if self.graph.has_node(nombre):
            # Ya existe: no tocar
            return
        self.graph.add_node(nombre, tipo=tipo)

    def _add_similarity_edges(
        self,
        events: list[dict[str, Any]],
        embedder: EventEmbedder | None,
        threshold: float,
    ) -> None:
        """Conecta pares de eventos con similitud coseno > threshold."""
        if embedder is None:
            try:
                embedder = EventEmbedder.get_instance()
            except RuntimeError:
                logger.warning(
                    "Embedder no disponible. Saltando aristas de similitud."
                )
                return

        if not embedder.events or embedder.embeddings is None:
            logger.warning("Embedder sin eventos cargados. Saltando similitud.")
            return

        # Verificar que los eventos coinciden
        if len(embedder.events) != len(events):
            logger.warning(
                f"Embedder tiene {len(embedder.events)} eventos, "
                f"pero se pasaron {len(events)}. Saltando similitud."
            )
            return

        embeddings = embedder.embeddings
        n = len(events)
        logger.info(f"Calculando similitudes para {n} eventos (umbral={threshold})...")

        # Distancias por pares (coseno, ya normalizados → producto punto)
        sim_matrix = embeddings @ embeddings.T

        # Iterar solo la mitad superior (simetría)
        n_edges = 0
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim > threshold:
                    id_i = self._event_id(events[i])
                    id_j = self._event_id(events[j])
                    self.graph.add_edge(
                        id_i, id_j,
                        tipo="similar_a",
                        peso=sim,
                    )
                    n_edges += 1

        logger.info(f"Añadidas {n_edges} aristas de similitud.")

    # ---------------------------------------------------------
    # PAGERANK Y RANKING
    # ---------------------------------------------------------

    def pagerank_events(self, alpha: float = 0.85) -> dict[str, float]:
        """
        Devuelve el PageRank de cada evento (por su título).

        Returns:
            dict {titulo_evento: score}
        """
        if self.graph.number_of_nodes() == 0:
            return {}

        # PageRank sobre grafo no dirigido equivalente
        pr = nx.pagerank(self.graph, alpha=alpha)

        # Filtrar solo eventos, mapeando id → título
        result: dict[str, float] = {}
        for node, score in pr.items():
            node_data = self.graph.nodes.get(node, {})
            if node_data.get("tipo") == "evento":
                # Recuperar el evento original
                ev = self._get_event_by_node(node)
                if ev:
                    titulo = ev.get("basic_info", {}).get("title", node)
                    result[titulo] = score

        return result

    def top_eventos_por_pagerank(self, k: int = 10) -> list[tuple[str, float]]:
        """Devuelve los top-k eventos por PageRank."""
        scores = self.pagerank_events()
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

    # ---------------------------------------------------------
    # RAZONAMIENTO MULTI-HOP
    # ---------------------------------------------------------

    def enriquecer(
        self,
        eventos_candidatos: list[dict[str, Any]],
        query: str,
        k: int = 10,
    ) -> list[tuple[dict[str, Any], float]]:
        """
        Enriquece una lista de eventos con un score del grafo.

        Para cada evento:
        - Bonus si sus vecinos (ciudad, categoría, artista...) coinciden
          con la query.
        - Bonus por PageRank (centralidad).

        Returns:
            Lista ordenada de (evento, score_grafo).
        """
        if self.graph.number_of_nodes() == 0:
            return [(ev, 0.0) for ev in eventos_candidatos]

        pr = nx.pagerank(self.graph) if self.graph.number_of_nodes() > 0 else {}
        query_lower = query.lower()
        resultados: list[tuple[dict[str, Any], float]] = []

        for ev in eventos_candidatos:
            ev_id = self._event_id(ev)
            score = 0.0

            if self.graph.has_node(ev_id):
                # Bonus por coincidencia con vecinos
                for vecino in self.graph.successors(ev_id):
                    vecino_lower = str(vecino).lower()
                    if query_lower in vecino_lower:
                        # Bonus según tipo de arista
                        for _, attrs in self.graph.get_edge_data(ev_id, vecino).items():
                            tipo = attrs.get("tipo", "")
                            if tipo == "similar_a":
                                score += attrs.get("peso", 0.1) * 1.5
                            elif tipo in ("ocurre_en", "ocurre_en_venue"):
                                score += 0.25
                            elif tipo in ("es_de_categoria", "tiene_artista"):
                                score += 0.2
                            else:
                                score += 0.1

                # Bonus por centralidad (PageRank)
                score += pr.get(ev_id, 0.0) * 100  # escalar

            resultados.append((ev, score))

        resultados.sort(key=lambda x: x[1], reverse=True)
        return resultados[:k]

    # ---------------------------------------------------------
    # PERSISTENCIA
    # ---------------------------------------------------------

    def save(self, path: Path | str | None = None) -> Path:
        """Guarda el grafo como GraphML."""
        if path is None:
            path = settings.graph_dir / "grafo_eventos.graphml"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        nx.write_graphml(self.graph, str(path))
        logger.info(f"Grafo guardado en {path}")
        return path

    @classmethod
    def load(cls, path: Path | str | None = None) -> KnowledgeGraph:
        """Carga un grafo desde GraphML."""
        if path is None:
            path = settings.graph_dir / "grafo_eventos.graphml"
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"No existe el grafo: {path}")

        kg = cls()
        kg.graph = nx.read_graphml(str(path))
        logger.info(
            f"Grafo cargado desde {path}: "
            f"{kg.graph.number_of_nodes()} nodos, "
            f"{kg.graph.number_of_edges()} aristas"
        )
        return kg

    # ---------------------------------------------------------
    # UTILIDAD
    # ---------------------------------------------------------

    @staticmethod
    def _event_id(ev: dict[str, Any]) -> str:
        """ID determinista de un evento."""
        return ev.get("id") or ev.get("basic_info", {}).get("title", "unknown")

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        """Parsea fecha ISO 8601."""
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _get_event_by_node(self, node_id: str) -> dict[str, Any] | None:
        """Recupera el evento original desde un nodo del grafo."""
        node_data = self.graph.nodes.get(node_id, {})
        if node_data.get("tipo") != "evento":
            return None
        raw = node_data.get("data")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def num_nodes(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def num_edges(self) -> int:
        return self.graph.number_of_edges()

    def estadisticas(self) -> dict[str, Any]:
        """Devuelve estadísticas del grafo por tipo de nodo/arista."""
        tipos_nodos: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            tipo = data.get("tipo", "desconocido")
            tipos_nodos[tipo] = tipos_nodos.get(tipo, 0) + 1

        tipos_aristas: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            tipo = data.get("tipo", "desconocida")
            tipos_aristas[tipo] = tipos_aristas.get(tipo, 0) + 1

        return {
            "num_nodos": self.num_nodes,
            "num_aristas": self.num_edges,
            "nodos_por_tipo": tipos_nodos,
            "aristas_por_tipo": tipos_aristas,
        }


# =============================================================
# API DE CONVENIENCIA
# =============================================================

def construir_grafo(
    events: list[dict[str, Any]],
    embedder: EventEmbedder | None = None,
) -> KnowledgeGraph:
    """Construye y devuelve un KnowledgeGraph listo para usar."""
    kg = KnowledgeGraph()
    kg.build(events, embedder=embedder)
    return kg