"""
Módulo de procesamiento y normalización de eventos.

Transforma datos crudos de PredictHQ, SeatGeek y Ticketmaster
en un formato enriquecido y unificado (mismo esquema que simulation.py).

Uso:
    from eventide.core.processing import EventProcessor, detect_source_from_filename

    processor = EventProcessor()
    evento_limpio = processor.process_event(raw_data, source="predicthq")
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from eventide.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================
# UTILIDADES
# =============================================================

def calcular_hash_json(data: dict[str, Any]) -> str:
    """Hash MD5 determinista de un dict JSON (para detectar cambios)."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(json_str.encode("utf-8")).hexdigest()


def detect_source_from_filename(filename: str) -> str | None:
    """Detecta la fuente a partir del nombre del archivo."""
    fname = filename.lower()
    if "predicthq" in fname:
        return "predicthq"
    if "seatgeek" in fname:
        return "seatgeek"
    if "ticketmaster" in fname or fname.startswith("tm_") or "_tm_" in fname:
        return "ticketmaster"
    return None


# =============================================================
# PROCESADOR PRINCIPAL
# =============================================================

class EventProcessor:
    """
    Procesador de eventos multi-fuente.

    Detecta la fuente, aplica el procesamiento específico y devuelve
    un evento con estructura unificada.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict, dict], None]] = {
            "predicthq": self._process_predicthq,
            "seatgeek": self._process_seatgeek,
            "ticketmaster": self._process_ticketmaster,
        }

    # ---------------------------------------------------------
    # API PÚBLICA
    # ---------------------------------------------------------

    def process_event(
        self,
        raw_data: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        """
        Procesa un evento crudo y devuelve el formato enriquecido.

        Si ocurre un error, devuelve un dict con clave "error" en vez de lanzar.
        """
        source = source.lower()
        if source not in self._handlers:
            raise ValueError(
                f"Fuente no soportada: {source}. Válidas: {list(self._handlers)}"
            )

        evento = self._empty_event(source, raw_data)

        try:
            self._handlers[source](raw_data, evento)
            self._post_process(evento)
            self._validate(evento)
            evento["metadata"]["raw_hash"] = calcular_hash_json(raw_data)
            return evento

        except Exception as e:
            error_id = str(uuid.uuid4())
            logger.error(f"[{source}] Error procesando evento {error_id}: {e}")
            return {
                "error": {
                    "id": error_id,
                    "message": str(e),
                    "source": source,
                    "original_id": raw_data.get("id"),
                },
                "metadata": {
                    "processing_timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "processing_error",
                },
            }

    def process_folder(
        self,
        input_dir: Path,
        output_dir: Path,
        verbose: bool = True,
    ) -> dict[str, int]:
        """
        Procesa todos los .json de una carpeta y los guarda en otra.

        Returns:
            Dict con estadísticas: {processed, errors, skipped}.
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = {"processed": 0, "errors": 0, "skipped": 0}

        for filepath in sorted(input_dir.glob("*.json")):
            source = detect_source_from_filename(filepath.name)
            if not source:
                stats["skipped"] += 1
                if verbose:
                    logger.warning(f"[SKIP] Fuente no detectada: {filepath.name}")
                continue

            try:
                with filepath.open("r", encoding="utf-8") as f:
                    raw = json.load(f)

                evento = self.process_event(raw, source)

                if "error" in evento:
                    stats["errors"] += 1
                    if verbose:
                        logger.error(
                            f"[ERROR] {filepath.name}: {evento['error']['message']}"
                        )
                    continue

                out_path = output_dir / f"{filepath.stem}_enhanced.json"
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(evento, f, ensure_ascii=False, indent=2)

                stats["processed"] += 1
                if verbose:
                    logger.info(f"[OK] {filepath.name} → {out_path.name}")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[ERROR] {filepath.name}: {e}")

        if verbose:
            logger.info(
                f"Procesamiento completado: "
                f"{stats['processed']} OK, {stats['errors']} errores, "
                f"{stats['skipped']} omitidos"
            )

        return stats

    # ---------------------------------------------------------
    # ESTRUCTURA BASE
    # ---------------------------------------------------------

    @staticmethod
    def _empty_event(source: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Devuelve el esqueleto de un evento vacío."""
        return {
            "id": raw.get("id") or f"evt_{uuid.uuid4().hex[:12]}",
            "metadata": {
                "source": source,
                "processing_timestamp": datetime.now(timezone.utc).isoformat(),
                "original_id": raw.get("id"),
                "event_version": "2.1",
                "raw_hash": None,
            },
            "basic_info": {
                "title": None,
                "description": None,
                "status": "confirmed",
                "visibility": "public",
            },
            "classification": {
                "primary_category": None,
                "categories": [],
                "tags": [],
            },
            "temporal_info": {
                "start": None,
                "end": None,
                "timezone": None,
                "duration_minutes": None,
                "is_recurring": False,
                "is_tba": False,
            },
            "spatial_info": {
                "venue": {
                    "name": None,
                    "full_address": None,
                    "address_components": {},
                    "location": {
                        "latitude": None,
                        "longitude": None,
                        "geo_accuracy": None,
                    },
                },
                "area": {
                    "city": None,
                    "region": None,
                    "country": None,
                },
            },
            "participants": {
                "performers": [],
                "organizers": [],
            },
            "external_references": {
                "urls": [],
                "images": [],
            },
            "raw_data_metadata": {
                "significant_fields_preserved": [],
                "source_specific": {},
            },
        }

    # ---------------------------------------------------------
    # HANDLERS POR FUENTE
    # ---------------------------------------------------------

    def _process_predicthq(self, raw: dict[str, Any], ev: dict[str, Any]) -> None:
        """Procesamiento para eventos de PredictHQ."""
        # Basic info
        ev["basic_info"]["title"] = raw.get("title")
        ev["basic_info"]["description"] = raw.get("description")

        # Clasificación
        ev["classification"]["primary_category"] = raw.get("category")
        ev["classification"]["tags"] = raw.get("labels", [])

        # Temporal
        self._fill_temporal(
            ev,
            start=raw.get("start"),
            end=raw.get("end"),
            timezone=raw.get("timezone"),
            duration=raw.get("duration"),
        )

        # Spatial — normalizar location
        location_raw = raw.get("location")
        if isinstance(location_raw, list) and len(location_raw) >= 2:
            location = {"lat": location_raw[0], "lon": location_raw[1]}
        elif isinstance(location_raw, dict):
            location = location_raw
        else:
            location = {}

        # Normalizar entities (PredictHQ a veces las devuelve como listas anidadas)
        entities_raw = raw.get("entities") or []
        entities: list[dict[str, Any]] = []
        for e in entities_raw:
            if isinstance(e, dict):
                entities.append(e)
            elif isinstance(e, list):
                for sub in e:
                    if isinstance(sub, dict):
                        entities.append(sub)

        venue_entity = next(
            (e for e in entities if e.get("type") == "venue"), None
        )
        if venue_entity:
            ev["spatial_info"]["venue"].update({
                "name": venue_entity.get("name"),
                "full_address": venue_entity.get("formatted_address"),
                "location": {
                    "latitude": location.get("lat"),
                    "longitude": location.get("lon"),
                    "geo_accuracy": "high",
                },
            })
        elif location.get("lat") is not None and location.get("lon") is not None:
            ev["spatial_info"]["venue"]["location"] = {
                "latitude": location.get("lat"),
                "longitude": location.get("lon"),
                "geo_accuracy": "medium",
            }

        # Performers
        performers = [
            e for e in entities if e.get("type") in ("person", "performer")
        ]
        ev["participants"]["performers"] = [
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "role": "main" if p.get("type") == "person" else "supporting",
            }
            for p in performers
        ]

        # URLs
        if raw.get("id"):
            ev["external_references"]["urls"].append({
                "type": "source",
                "url": f"https://predicthq.com/events/{raw['id']}",
            })

        ev["raw_data_metadata"]["significant_fields_preserved"] = [
            "scope", "labels", "entities",
        ]
        ev["raw_data_metadata"]["source_specific"] = {
            "scope": raw.get("scope"),
            "entity_count": len(entities),
        }

    def _process_seatgeek(self, raw: dict[str, Any], ev: dict[str, Any]) -> None:
        """Procesamiento para eventos de SeatGeek."""
        ev["basic_info"]["title"] = raw.get("title")

        # Taxonomías
        taxonomies = raw.get("taxonomies") or []
        if taxonomies:
            ev["classification"]["primary_category"] = taxonomies[0].get("name")
            ev["classification"]["categories"] = [
                t.get("name") for t in taxonomies[1:] if t.get("name")
            ]

        # Temporal
        venue = raw.get("venue") or {}
        self._fill_temporal(
            ev,
            start=raw.get("datetime_local"),
            timezone=venue.get("timezone"),
        )

        # Spatial
        location = venue.get("location") or {}
        venue_name = venue.get("name") or (
            f"Venue en {venue.get('city')}" if venue.get("city") else None
        )
        full_address = ", ".join(
            filter(None, [
                venue.get("address"),
                venue.get("city"),
                venue.get("state"),
                venue.get("country"),
            ])
        )
        ev["spatial_info"]["venue"].update({
            "name": venue_name,
            "full_address": full_address or None,
            "address_components": {
                "street": venue.get("address"),
                "city": venue.get("city"),
                "state": venue.get("state"),
                "country": venue.get("country"),
                "postal_code": venue.get("postal_code"),
            },
            "location": {
                "latitude": location.get("lat"),
                "longitude": location.get("lon"),
                "geo_accuracy": "high" if location.get("lat") else None,
            },
        })
        ev["spatial_info"]["area"] = {
            "city": venue.get("city"),
            "region": venue.get("state"),
            "country": venue.get("country"),
        }

        # Performers
        performers = raw.get("performers") or []
        ev["participants"]["performers"] = [
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "role": "main" if p.get("primary") else "supporting",
            }
            for p in performers
        ]

        # URLs e imágenes
        if raw.get("url"):
            ev["external_references"]["urls"].append({
                "type": "ticketing",
                "url": raw["url"],
            })
        for performer in performers:
            if performer.get("image"):
                ev["external_references"]["images"].append({
                    "type": "performer",
                    "url": performer["image"],
                })

        ev["raw_data_metadata"]["significant_fields_preserved"] = [
            "taxonomies", "performers", "stats",
        ]
        ev["raw_data_metadata"]["source_specific"] = {
            "score": raw.get("score"),
            "popularity": (raw.get("stats") or {}).get("event_count"),
        }

    def _process_ticketmaster(self, raw: dict[str, Any], ev: dict[str, Any]) -> None:
        """Procesamiento para eventos de Ticketmaster."""
        ev["basic_info"]["title"] = raw.get("name")
        ev["basic_info"]["description"] = raw.get("info")

        # Estado
        status_code = (
            (raw.get("dates") or {}).get("status") or {}
        ).get("code")
        if status_code == "cancelled":
            ev["basic_info"]["status"] = "cancelled"

        # Clasificación
        classifications = raw.get("classifications") or []
        if classifications:
            c = classifications[0]
            ev["classification"]["primary_category"] = (
                (c.get("segment") or {}).get("name")
            )
            ev["classification"]["categories"] = [
                v for v in [
                    (c.get("genre") or {}).get("name"),
                    (c.get("subGenre") or {}).get("name"),
                ] if v
            ]

        # Temporal
        dates = raw.get("dates") or {}
        start = dates.get("start") or {}
        self._fill_temporal(
            ev,
            start=start.get("localDate"),
            timezone=dates.get("timezone"),
            is_tba=bool(start.get("timeTBA") or start.get("dateTBA")),
        )

        # Spatial
        venue = raw.get("venue") or {}
        venue_name = venue.get("name") or (
            f"{venue.get('address')} ({venue.get('city')})"
            if venue.get("address") and venue.get("city")
            else (f"Venue en {venue.get('city')}" if venue.get("city") else None)
        )
        full_address = ", ".join(
            filter(None, [
                venue.get("address"),
                venue.get("city"),
                venue.get("country"),
            ])
        )
        ev["spatial_info"]["venue"].update({
            "name": venue_name,
            "full_address": full_address or None,
            "address_components": {
                "street": venue.get("address"),
                "city": venue.get("city"),
                "country": venue.get("country"),
            },
        })
        ev["spatial_info"]["area"] = {
            "city": venue.get("city"),
            "country": venue.get("country"),
        }

        # Performers
        attractions = raw.get("attractions") or []
        ev["participants"]["performers"] = [
            {
                "name": a.get("name"),
                "type": a.get("type"),
                "role": "main",
            }
            for a in attractions
        ]

        # URLs
        if raw.get("url"):
            ev["external_references"]["urls"].append({
                "type": "ticketing",
                "url": raw["url"],
            })

        ev["raw_data_metadata"]["significant_fields_preserved"] = [
            "classifications", "attractions", "dates",
        ]
        ev["raw_data_metadata"]["source_specific"] = {
            "event_type": raw.get("type"),
            "span_multiple_days": dates.get("spanMultipleDays"),
        }

    # ---------------------------------------------------------
    # TEMPORAL (común)
    # ---------------------------------------------------------

    def _fill_temporal(
        self,
        ev: dict[str, Any],
        start: str | None = None,
        end: str | None = None,
        timezone: str | None = None,
        duration: int | None = None,
        is_tba: bool = False,
    ) -> None:
        """Rellena la sección temporal con normalización."""
        t = ev["temporal_info"]

        if timezone:
            t["timezone"] = timezone

        t["start"] = self._normalize_datetime(start)
        t["end"] = self._normalize_datetime(end)

        if not t["end"] and duration:
            t["duration_minutes"] = round(duration / 60)

        t["is_tba"] = is_tba

    @staticmethod
    def _normalize_datetime(value: str | None) -> str | None:
        """Normaliza fecha/hora a ISO 8601. Devuelve None si falla."""
        if not value:
            return None
        try:
            if "T" in value:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.isoformat()
            dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.date().isoformat()
        except (ValueError, TypeError):
            return value

    # ---------------------------------------------------------
    # POST-PROCESAMIENTO
    # ---------------------------------------------------------

    @staticmethod
    def _post_process(ev: dict[str, Any]) -> None:
        """Limpia campos vacíos y garantiza consistencia."""
        def clean(d: Any) -> Any:
            if not isinstance(d, dict):
                return d
            return {
                k: clean(v) for k, v in d.items()
                if v not in (None, "", [], {})
            }

        cleaned = clean(ev)

        cleaned.setdefault("classification", {}).setdefault("categories", [])
        cleaned.setdefault("classification", {}).setdefault("tags", [])
        cleaned.setdefault("participants", {}).setdefault("performers", [])
        cleaned.setdefault("participants", {}).setdefault("organizers", [])
        cleaned.setdefault("external_references", {}).setdefault("urls", [])
        cleaned.setdefault("external_references", {}).setdefault("images", [])

        ev.clear()
        ev.update(cleaned)

    # ---------------------------------------------------------
    # VALIDACIÓN
    # ---------------------------------------------------------

    @staticmethod
    def _validate(ev: dict[str, Any]) -> None:
        """Valida campos obligatorios. Lanza ValueError si faltan."""
        missing: list[str] = []

        if not ev.get("basic_info", {}).get("title"):
            missing.append("title")
        if not ev.get("temporal_info", {}).get("start"):
            missing.append("start date")

        venue = ev.get("spatial_info", {}).get("venue", {})
        loc = venue.get("location", {})
        has_venue = bool(
            venue.get("name")
            or venue.get("full_address")
            or (loc.get("latitude") and loc.get("longitude"))
        )
        if not has_venue:
            missing.append("venue info")

        if missing:
            raise ValueError(f"Faltan campos obligatorios: {', '.join(missing)}")