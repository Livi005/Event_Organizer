"""Tests para el módulo de procesamiento."""

import pytest

from eventide.core.processing import (
    EventProcessor,
    calcular_hash_json,
    detect_source_from_filename,
)


# === Utilidades ===

def test_detect_source_predicthq():
    assert detect_source_from_filename("predicthq_evento_1.json") == "predicthq"
    assert detect_source_from_filename("PREDICTHQ_1.JSON") == "predicthq"


def test_detect_source_seatgeek():
    assert detect_source_from_filename("seatgeek_evento_2.json") == "seatgeek"


def test_detect_source_ticketmaster():
    assert detect_source_from_filename("ticketmaster_evento_3.json") == "ticketmaster"
    assert detect_source_from_filename("tm_evento_3.json") == "ticketmaster"


def test_detect_source_unknown():
    assert detect_source_from_filename("random.json") is None


def test_hash_json_deterministic():
    a = {"x": 1, "y": [1, 2, 3]}
    b = {"y": [1, 2, 3], "x": 1}
    assert calcular_hash_json(a) == calcular_hash_json(b)


# === PredictHQ ===

def test_process_predicthq_valid():
    raw = {
        "id": "phq_1",
        "title": "Concierto en Madrid",
        "description": "Un concierto",
        "category": "concerts",
        "labels": ["music", "live"],
        "start": "2025-06-15T21:00:00Z",
        "end": "2025-06-15T23:00:00Z",
        "timezone": "Europe/Madrid",
        "duration": 7200,
        "location": [40.4168, -3.7038],
        "entities": [
            {"type": "venue", "name": "Wizink Center", "formatted_address": "Madrid"},
            {"type": "person", "name": "Rosalía"},
        ],
    }
    processor = EventProcessor()
    ev = processor.process_event(raw, "predicthq")

    assert "error" not in ev
    assert ev["basic_info"]["title"] == "Concierto en Madrid"
    assert ev["classification"]["primary_category"] == "concerts"
    assert ev["temporal_info"]["start"] is not None
    assert ev["spatial_info"]["venue"]["name"] == "Wizink Center"
    assert len(ev["participants"]["performers"]) == 1
    assert ev["participants"]["performers"][0]["name"] == "Rosalía"
    assert ev["metadata"]["source"] == "predicthq"
    assert ev["metadata"]["raw_hash"] is not None


# === SeatGeek ===

def test_process_seatgeek_valid():
    raw = {
        "id": 123,
        "title": "Festival de Verano",
        "datetime_local": "2025-07-20T20:00:00",
        "url": "https://seatgeek.com/event/123",
        "venue": {
            "name": "Estadio Olímpico",
            "city": "Barcelona",
            "state": "Cataluña",
            "country": "España",
            "address": "Carrer X",
            "location": {"lat": 41.3874, "lon": 2.1686},
        },
        "taxonomies": [
            {"name": "music"},
            {"name": "festival"},
        ],
        "performers": [
            {"name": "Aitana", "primary": True, "image": "http://img/aitana.jpg"},
        ],
        "stats": {"event_count": 42},
    }
    processor = EventProcessor()
    ev = processor.process_event(raw, "seatgeek")

    assert "error" not in ev
    assert ev["basic_info"]["title"] == "Festival de Verano"
    assert ev["classification"]["primary_category"] == "music"
    assert ev["spatial_info"]["venue"]["name"] == "Estadio Olímpico"
    assert ev["spatial_info"]["area"]["city"] == "Barcelona"
    assert ev["participants"]["performers"][0]["name"] == "Aitana"
    assert ev["participants"]["performers"][0]["role"] == "main"
    assert len(ev["external_references"]["images"]) == 1


# === Ticketmaster ===

def test_process_ticketmaster_valid():
    raw = {
        "id": "tm_456",
        "name": "Final de Copa",
        "info": "Partido final",
        "type": "event",
        "url": "https://ticketmaster.com/event/456",
        "classifications": [
            {
                "segment": {"name": "Sports"},
                "genre": {"name": "Soccer"},
                "subGenre": {"name": "Club"},
            }
        ],
        "dates": {
            "start": {"localDate": "2025-08-15", "timeTBA": False},
            "timezone": "Europe/Madrid",
            "status": {"code": "onsale"},
            "spanMultipleDays": False,
        },
        "attractions": [
            {"name": "Real Madrid", "type": "team"},
        ],
        "venue": {
            "name": "Santiago Bernabéu",
            "city": "Madrid",
            "country": "España",
            "address": "Av. Concha Espina",
        },
    }
    processor = EventProcessor()
    ev = processor.process_event(raw, "ticketmaster")

    assert "error" not in ev
    assert ev["basic_info"]["title"] == "Final de Copa"
    assert ev["classification"]["primary_category"] == "Sports"
    assert ev["spatial_info"]["venue"]["name"] == "Santiago Bernabéu"
    assert ev["spatial_info"]["area"]["city"] == "Madrid"
    assert ev["participants"]["performers"][0]["name"] == "Real Madrid"


# === Errores ===

def test_process_invalid_source():
    processor = EventProcessor()
    with pytest.raises(ValueError):
        processor.process_event({}, "source_inexistente")


def test_process_missing_title_returns_error():
    raw = {
        "id": "x",
        "start": "2025-01-01T10:00:00Z",
        "location": [1.0, 2.0],
        "entities": [{"type": "venue", "name": "V"}],
    }
    processor = EventProcessor()
    ev = processor.process_event(raw, "predicthq")
    assert "error" in ev
    assert "title" in ev["error"]["message"].lower()


def test_process_missing_venue_returns_error():
    raw = {
        "id": "x",
        "title": "Evento sin venue",
        "start": "2025-01-01T10:00:00Z",
    }
    processor = EventProcessor()
    ev = processor.process_event(raw, "predicthq")
    assert "error" in ev
    assert "venue" in ev["error"]["message"].lower()


# === Carpeta completa ===

def test_process_folder_empty(tmp_path):
    inp = tmp_path / "in"
    out = tmp_path / "out"
    inp.mkdir()

    processor = EventProcessor()
    stats = processor.process_folder(inp, out, verbose=False)

    assert stats == {"processed": 0, "errors": 0, "skipped": 0}


def test_process_folder_with_files(tmp_path):
    import json

    inp = tmp_path / "in"
    out = tmp_path / "out"
    inp.mkdir()

    raw = {
        "id": "1",
        "title": "Test Event",
        "start": "2025-06-15T21:00:00Z",
        "location": [40.4, -3.7],
        "entities": [{"type": "venue", "name": "Test Venue"}],
    }
    (inp / "predicthq_evento_1.json").write_text(
        json.dumps(raw), encoding="utf-8"
    )

    processor = EventProcessor()
    stats = processor.process_folder(inp, out, verbose=False)

    assert stats["processed"] == 1
    assert (out / "predicthq_evento_1_enhanced.json").exists()