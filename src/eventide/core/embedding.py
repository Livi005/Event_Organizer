"""
Módulo de embeddings semánticos y búsqueda vectorial.

Implementa la clase `EventEmbedder` (singleton thread-safe) que:
- Construye representaciones textuales de eventos
- Genera embeddings con SentenceTransformers
- Construye índices FAISS (global + shards por ciudad)
- Realiza búsqueda semántica con filtros (ciudad, categoría, fechas)
- Persiste y carga los embeddings desde disco

Uso:
    from eventide.core.embedding import EventEmbedder

    embedder = EventEmbedder()
    embedder.generate_embeddings(eventos)
    embedder.build_index()
    resultados, scores = embedder.search("conciertos de rock en Madrid", k=10)
"""

from __future__ import annotations

import json
import pickle
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from eventide.config import settings
from eventide.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================
# UTILIDADES
# =============================================================

def load_events_from_folder(folder: Path | str) -> list[dict[str, Any]]:
    """Carga todos los .json de una carpeta como lista de eventos."""
    folder = Path(folder)
    events: list[dict[str, Any]] = []

    if not folder.exists():
        logger.warning(f"La carpeta {folder} no existe.")
        return events

    for filepath in sorted(folder.glob("*.json")):
        try:
            with filepath.open("r", encoding="utf-8") as f:
                events.append(json.load(f))
        except Exception as e:
            logger.error(f"Error leyendo {filepath.name}: {e}")

    logger.info(f"Cargados {len(events)} eventos desde {folder}")
    return events


def _make_aware(dt: datetime) -> datetime:
    """Convierte datetime naive a UTC-aware."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# =============================================================
# EVENT EMBEDDER (SINGLETON)
# =============================================================

class EventEmbedder:
    """
    Embedder singleton thread-safe para eventos.

    Atributos de clase (compartidos entre todas las instancias):
        _instance: la instancia única
        _lock: lock de creación
        _model: el modelo SentenceTransformer (cargado una vez)
    """

    _instance: ClassVar[EventEmbedder | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str | None = None):
        if getattr(self, "_initialized", False):
            return

        self.model_name = model_name or settings.model_name
        logger.info(f"Cargando modelo de embeddings: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.model.to("cpu")

        # Estado interno
        self.events: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None
        self.index: faiss.Index | None = None
        self.shards: dict[str, tuple[faiss.Index, list[dict[str, Any]]]] = {}
        self.metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": self.model_name,
            "version": "2.1",
        }

        self._initialized = True
        logger.info("EventEmbedder inicializado correctamente")

    # ---------------------------------------------------------
    # REPRESENTACIÓN TEXTUAL
    # ---------------------------------------------------------

    def build_event_text(self, event: dict[str, Any]) -> str:
        """
        Construye una representación textual rica de un evento.

        Es la parte MÁS IMPORTANTE para la calidad de la búsqueda:
        el texto que se embebe determina qué consultas lo recuperarán.
        """
        parts: list[str] = []

        # Básicos
        basic = event.get("basic_info", {})
        if basic.get("title"):
            parts.append(f"Título: {basic['title']}")
        if basic.get("description"):
            desc = basic["description"]
            # Truncar descripciones muy largas
            if len(desc) > 500:
                desc = desc[:500] + "..."
            parts.append(f"Descripción: {desc}")

        # Clasificación
        cls = event.get("classification", {})
        if cls.get("primary_category"):
            parts.append(f"Categoría: {cls['primary_category']}")
        if cls.get("categories"):
            parts.append(f"Subcategorías: {', '.join(cls['categories'])}")
        if cls.get("tags"):
            parts.append(f"Tags: {', '.join(cls['tags'])}")

        # Espacial
        spatial = event.get("spatial_info", {})
        venue = spatial.get("venue", {})
        if venue.get("name"):
            parts.append(f"Lugar: {venue['name']}")
        if venue.get("full_address"):
            parts.append(f"Dirección: {venue['full_address']}")
        area = spatial.get("area", {})
        if area.get("city"):
            parts.append(f"Ciudad: {area['city']}")
        if area.get("region"):
            parts.append(f"Región: {area['region']}")
        if area.get("country"):
            parts.append(f"País: {area['country']}")

        # Temporal
        temporal = event.get("temporal_info", {})
        if temporal.get("start"):
            parts.append(f"Fecha: {temporal['start']}")
        if temporal.get("duration_minutes"):
            parts.append(f"Duración: {temporal['duration_minutes']} minutos")

        # Participantes
        participants = event.get("participants", {})
        performers = participants.get("performers", [])
        names = [p.get("name", "").strip() for p in performers if p.get("name")]
        if names:
            parts.append(f"Artistas: {', '.join(names)}")

        organizers = participants.get("organizers", [])
        org_names = [o.get("name", "").strip() for o in organizers if o.get("name")]
        if org_names:
            parts.append(f"Organizadores: {', '.join(org_names)}")

        # Popularidad
        popularity = (
            event.get("raw_data_metadata", {})
            .get("source_specific", {})
            .get("popularity")
        )
        if popularity:
            parts.append(f"Popularidad: {popularity}")

        return ". ".join(parts) + "."

    # ---------------------------------------------------------
    # GENERACIÓN DE EMBEDDINGS
    # ---------------------------------------------------------

    def generate_embeddings(
        self,
        events: list[dict[str, Any]],
        batch_size: int = 32,
    ) -> np.ndarray:
        """Genera embeddings para una lista de eventos (normalizados L2)."""
        if not events:
            raise ValueError("La lista de eventos está vacía")

        logger.info(f"Generando embeddings para {len(events)} eventos...")
        self.events = events

        texts = [self.build_event_text(e) for e in events]
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        self.embeddings = embeddings.astype("float32")
        logger.info(f"Embeddings generados. Shape: {self.embeddings.shape}")
        return self.embeddings

    # ---------------------------------------------------------
    # ÍNDICE FAISS
    # ---------------------------------------------------------

    def build_index(self, index_type: str = "flat") -> faiss.Index:
        """
        Construye el índice FAISS para búsqueda por similitud.

        Args:
            index_type: "flat" (exacto, rápido para <100k) o
                        "ivf" (aproximado, para >100k).
        """
        if self.embeddings is None:
            raise ValueError("Primero genera embeddings con generate_embeddings()")

        dim = self.embeddings.shape[1]
        logger.info(f"Construyendo índice FAISS ({index_type}, dim={dim})...")

        if index_type == "flat":
            # Inner Product = similitud coseno (porque normalizamos)
            self.index = faiss.IndexFlatIP(dim)
        elif index_type == "ivf":
            nlist = min(100, len(self.embeddings) // 10)
            quantizer = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIVFFlat(quantizer, dim, nlist)
            self.index.train(self.embeddings)
            self.index.nprobe = 10
        else:
            raise ValueError(f"index_type no soportado: {index_type}")

        self.index.add(self.embeddings)
        logger.info(f"Índice construido. Total vectores: {self.index.ntotal}")
        return self.index

    def build_shards(self) -> dict[str, tuple[faiss.Index, list[dict[str, Any]]]]:
        """
        Construye índices separados por ciudad (shards).

        Esto permite búsquedas ultra-rápidas cuando se filtra por ciudad:
        en vez de buscar en todos los eventos, busca solo en el shard.
        """
        if not self.events or self.embeddings is None:
            raise ValueError("Primero genera embeddings")

        logger.info("Construyendo shards por ciudad...")

        # Agrupar por ciudad
        groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        for i, ev in enumerate(self.events):
            city = ev.get("spatial_info", {}).get("area", {}).get("city") or "unknown"
            groups[city].append((i, ev))

        self.shards = {}
        for city, items in groups.items():
            idxs = [i for i, _ in items]
            evs = [e for _, e in items]
            city_embeddings = self.embeddings[idxs]

            index = faiss.IndexFlatIP(city_embeddings.shape[1])
            index.add(city_embeddings)
            self.shards[city] = (index, evs)

        logger.info(
            f"Shards construidos: {len(self.shards)} ciudades, "
            f"tamaños: {[len(v[1]) for v in self.shards.values()]}"
        )
        return self.shards

    # ---------------------------------------------------------
    # BÚSQUEDA
    # ---------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 10,
        shard_key: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[float]]:
        """
        Búsqueda semántica simple.

        Args:
            query: texto de búsqueda.
            k: número de resultados.
            shard_key: si se indica, busca solo en ese shard (ciudad).

        Returns:
            (lista de eventos con campo "score", lista de scores)
        """
        if self.index is None and not self.shards:
            raise RuntimeError("Debes llamar a build_index() o build_shards() primero")

        q_vec = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        # Buscar en shard específico
        if shard_key and shard_key in self.shards:
            index, events = self.shards[shard_key]
            distances, indices = index.search(q_vec, min(k, len(events)))
            results = [
                {**events[i], "score": float(distances[0][j])}
                for j, i in enumerate(indices[0])
                if 0 <= i < len(events)
            ]
            scores = distances[0].tolist()
            return results, scores

        # Buscar en todos los shards (si existen)
        if self.shards:
            all_results: list[dict[str, Any]] = []
            for city, (index, events) in self.shards.items():
                distances, indices = index.search(q_vec, min(k, len(events)))
                for j, i in enumerate(indices[0]):
                    if 0 <= i < len(events):
                        all_results.append({
                            **events[i],
                            "score": float(distances[0][j]),
                        })
            all_results.sort(key=lambda x: x["score"], reverse=True)
            return all_results[:k], [r["score"] for r in all_results[:k]]

        # Buscar en el índice global
        distances, indices = self.index.search(q_vec, k)
        results = [
            {**self.events[i], "score": float(distances[0][j])}
            for j, i in enumerate(indices[0])
            if 0 <= i < len(self.events)
        ]
        return results, distances[0].tolist()

    def filtered_search(
        self,
        query: str,
        city: str | None = None,
        category: str | None = None,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
        k: int = 60,
    ) -> tuple[list[dict[str, Any]], list[float]]:
        """
        Búsqueda semántica con filtros post-ranking.

        Los filtros se aplican DESPUÉS de la búsqueda vectorial
        (por eficiencia: FAISS no soporta filtros nativos fácilmente).
        """
        # Buscar más candidatos de los necesarios, luego filtrar
        candidates, _ = self.search(query, k=k * 3)
        results = self._apply_filters(
            candidates, city=city, category=category,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        )
        results = results[:k]
        return results, [r["score"] for r in results]

    @staticmethod
    def _apply_filters(
        events: list[dict[str, Any]],
        city: str | None = None,
        category: str | None = None,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
    ) -> list[dict[str, Any]]:
        """Aplica filtros de ciudad, categoría y rango de fechas."""
        filtered = events

        if city:
            city_lower = city.lower().strip()
            filtered = [
                e for e in filtered
                if (e.get("spatial_info", {})
                    .get("area", {})
                    .get("city", "") or "").lower().strip() == city_lower
            ]

        if category:
            cat_lower = category.lower().strip()
            filtered = [
                e for e in filtered
                if cat_lower in (
                    e.get("classification", {})
                    .get("primary_category", "") or ""
                ).lower()
                or any(
                    cat_lower in c.lower()
                    for c in e.get("classification", {}).get("categories", [])
                )
            ]

        if fecha_inicio or fecha_fin:
            start_dt = _parse_iso(fecha_inicio) if fecha_inicio else None
            end_dt = _parse_iso(fecha_fin) if fecha_fin else None
            filtered = [
                e for e in filtered
                if _event_in_range(e, start_dt, end_dt)
            ]

        return filtered

    # ---------------------------------------------------------
    # PERSISTENCIA
    # ---------------------------------------------------------

    def save(self, output_dir: Path | str | None = None) -> None:
        """Guarda índice, metadata y embeddings en disco."""
        output_dir = Path(output_dir or settings.embeddings_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.index is not None:
            faiss.write_index(self.index, str(output_dir / "eventos.index"))

        if self.events:
            with (output_dir / "eventos_metadata.pkl").open("wb") as f:
                pickle.dump({"events": self.events, "metadata": self.metadata}, f)

        if self.embeddings is not None:
            np.save(output_dir / "eventos_embeddings.npy", self.embeddings)

        logger.info(f"Datos guardados en {output_dir}")

    @classmethod
    def load(cls, input_dir: Path | str | None = None) -> EventEmbedder:
        """Carga índice, metadata y embeddings desde disco."""
        input_dir = Path(input_dir or settings.embeddings_dir)

        path_index = input_dir / "eventos.index"
        path_meta = input_dir / "eventos_metadata.pkl"
        path_emb = input_dir / "eventos_embeddings.npy"

        if not all(p.exists() for p in (path_index, path_meta, path_emb)):
            raise FileNotFoundError(
                f"Faltan archivos de embeddings en {input_dir}"
            )

        instance = cls()
        instance.index = faiss.read_index(str(path_index))

        with path_meta.open("rb") as f:
            data = pickle.load(f)
            instance.events = data["events"]
            instance.metadata = data.get("metadata", {})

        instance.embeddings = np.load(path_emb).astype("float32")
        instance.build_shards()

        logger.info(f"Cargados {len(instance.events)} eventos desde {input_dir}")
        return instance

    # ---------------------------------------------------------
    # UTILIDAD
    # ---------------------------------------------------------

    @classmethod
    def get_instance(cls) -> EventEmbedder:
        """Devuelve la instancia singleton (debe estar inicializada)."""
        if cls._instance is None or not getattr(cls._instance, "_initialized", False):
            raise RuntimeError("EventEmbedder no ha sido inicializado")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reinicia el singleton (útil en tests)."""
        with cls._lock:
            cls._instance = None

    @property
    def num_events(self) -> int:
        return len(self.events)

    @property
    def num_shards(self) -> int:
        return len(self.shards)


# =============================================================
# HELPERS DE FECHAS
# =============================================================

def _parse_iso(value: str) -> datetime | None:
    """Parsea ISO 8601 y devuelve datetime UTC-aware. None si falla."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _make_aware(dt)
    except (ValueError, AttributeError):
        return None


def _event_in_range(
    event: dict[str, Any],
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> bool:
    """Comprueba si un evento está en el rango de fechas."""
    raw = event.get("temporal_info", {}).get("start")
    if not raw:
        return False
    fecha = _parse_iso(raw)
    if fecha is None:
        return False
    if start_dt and fecha < start_dt:
        return False
    if end_dt and fecha > end_dt:
        return False
    return True