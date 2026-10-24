"""
Modulo de simulacion para Eventide.

Genera:
- Eventos sinteticos realistas (con coordenadas reales, fechas, categorias)
- Escenarios de usuario (preferencias, restricciones)
- Perfiles de usuario (joven fiestero, familia, turista cultural, etc.)
- Replicas Monte Carlo para analisis estadistico

NOTA IMPORTANTE SOBRE EL ALCANCE GEOGRAFICO
============================================
Este modulo usa ciudades de demo SOLO para datos sinteticos y testing.
El sistema es AGNOSTICO AL PAIS: los datos reales provienen de PredictHQ,
SeatGeek y Ticketmaster, que cubren eventos en todo el mundo.

Las ciudades de demo abarcan Europa, America, Asia y Oceania para
reflejar ese alcance global.
"""

from __future__ import annotations

import random
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from eventide.config import settings

# =============================================================
# CIUDADES DE DEMO (multi-continente)
# =============================================================

CIUDADES_DEMO: dict[str, tuple[float, float]] = {
    # --- Europa ---
    "Madrid":       (40.4168, -3.7038),
    "Barcelona":    (41.3874,  2.1686),
    "Valencia":     (39.4699, -0.3763),
    "Sevilla":      (37.3891, -5.9845),
    "Bilbao":       (43.2630, -2.9350),
    "Malaga":       (36.7213, -4.4214),
    "Zaragoza":     (41.6488, -0.8891),
    "Granada":      (37.1773, -3.5986),
    "Palma":        (39.5696,  2.6502),
    "Ibiza":        (38.9067,  1.4206),
    "Paris":        (48.8566,  2.3522),
    "Berlin":       (52.5200, 13.4050),
    "Rome":         (41.9028, 12.4964),
    "London":       (51.5074, -0.1278),
    "Amsterdam":    (52.3676,  4.9041),
    # --- America ---
    "New York":     (40.7128, -74.0060),
    "Mexico DF":    (19.4326, -99.1332),
    "Buenos Aires": (-34.6037, -58.3816),
    "Bogota":       (4.7110, -74.0721),
    "La Habana":    (23.1136, -82.3666),
    "Santiago":     (-33.4489, -70.6693),
    "Lima":         (-12.0464, -77.0428),
    # --- Asia / Oceania ---
    "Tokyo":        (35.6762, 139.6503),
    "Sydney":       (-33.8688, 151.2093),
    "Singapore":    (1.3521, 103.8198),
}

# Alias de compatibilidad
CIUDADES_ES = CIUDADES_DEMO

# =============================================================
# CATEGORIAS Y ARTISTAS FICTICIOS
# =============================================================

CATEGORIAS = [
    "concerts", "theater", "sports", "arts",
    "technology", "food", "literature", "wellness",
    "festivals", "conferences",
]

ARTISTAS_POR_CATEGORIA: dict[str, list[str]] = {
    "concerts":    ["Rosalia", "Bad Bunny", "C. Tangana", "Aitana", "Vetusta Morla"],
    "theater":     ["Compania Nacional", "Teatro Real", "La Cubana", "Yllana"],
    "sports":      ["Real Madrid", "FC Barcelona", "Atletico", "Seleccion"],
    "arts":        ["Museo del Prado", "MACBA", "Guggenheim", "CaixaForum"],
    "technology":  ["Google IO", "AWS Summit", "PyConES", "WordCamp"],
    "food":        ["Madrid Fusion", "San Sebastian Gastronomika", "Feria del Vino"],
    "literature":  ["Feria del Libro", "Hay Festival", "Premio Cervantes"],
    "wellness":    ["YogaFest", "Mindfulness Day", "Retiro Zen"],
    "festivals":   ["Primavera Sound", "Mad Cool", "FIB", "Sonar"],
    "conferences": ["TedX", "South Summit", "Mobile World Congress"],
}


# =============================================================
# GENERACION DE EVENTOS SINTETICOS
# =============================================================

def generar_eventos(
    n: int = 100,
    seed: int | None = 42,
    base_date: datetime | None = None,
    horizonte_dias: int = 90,
) -> list[dict[str, Any]]:
    """
    Genera `n` eventos sinteticos en el rango [hoy, hoy + horizonte_dias].

    Args:
        n: numero de eventos a generar.
        seed: semilla para reproducibilidad.
        base_date: fecha base. Si None, usa hoy.
        horizonte_dias: cuantos dias hacia adelante generar eventos.
                        Por defecto 90 (3 meses).
    """
    if seed is not None:
        random.seed(seed)

    if base_date is None:
        base_date = datetime.now(timezone.utc)

    eventos: list[dict[str, Any]] = []

    for i in range(n):
        ciudad = random.choice(list(CIUDADES_DEMO.keys()))
        lat_base, lon_base = CIUDADES_DEMO[ciudad]
        categoria = random.choice(CATEGORIAS)
        artistas = random.sample(
            ARTISTAS_POR_CATEGORIA[categoria],
            k=min(2, len(ARTISTAS_POR_CATEGORIA[categoria])),
        )

        # Fecha del evento: dentro del horizonte
        dias_offset = random.randint(0, horizonte_dias)
        hora = random.randint(18, 22)
        start_dt = (base_date + timedelta(days=dias_offset)).replace(
            hour=hora, minute=0, second=0, microsecond=0
        )
        duracion_min = random.choice([60, 90, 120, 150, 180])
        end_dt = start_dt + timedelta(minutes=duracion_min)

        # Coordenadas con jitter
        lat = lat_base + random.uniform(-0.05, 0.05)
        lon = lon_base + random.uniform(-0.05, 0.05)

        evento: dict[str, Any] = {
            "id": f"evt_{i:06d}_{_hash_id(f'{ciudad}{categoria}{i}')}",
            "metadata": {
                "source": "synthetic",
                "processing_timestamp": datetime.now(timezone.utc).isoformat(),
                "original_id": f"synth_{i}",
                "event_version": "2.1",
                "raw_hash": _hash_id(f"raw_{i}"),
            },
            "basic_info": {
                "title": f"{_titulo_evento(categoria)} en {ciudad}",
                "description": (
                    f"Evento de {categoria} que se celebra en {ciudad}. "
                    f"Participan {', '.join(artistas)}."
                ),
                "status": "confirmed",
                "visibility": "public",
            },
            "classification": {
                "primary_category": categoria,
                "categories": [categoria],
                "tags": artistas,
            },
            "temporal_info": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "timezone": "UTC",
                "duration_minutes": duracion_min,
                "is_recurring": False,
                "is_tba": False,
            },
            "spatial_info": {
                "venue": {
                    "name": f"Venue {random.choice(['Central', 'Norte', 'Sur', 'Este', 'Oeste'])}",
                    "full_address": f"Calle {random.randint(1, 200)}, {ciudad}",
                    "location": {
                        "latitude": lat,
                        "longitude": lon,
                        "geo_accuracy": "high",
                    },
                },
                "area": {
                    "city": ciudad,
                    "region": _region_de(ciudad),
                    "country": _pais_de(ciudad),
                },
            },
            "participants": {
                "performers": [
                    {"name": a, "type": "artist", "role": "main"} for a in artistas
                ],
                "organizers": [],
            },
            "external_references": {
                "urls": [
                    {"type": "source", "url": f"https://example.com/event/{i}"}
                ],
                "images": [],
            },
            "raw_data_metadata": {
                "significant_fields_preserved": [],
                "source_specific": {
                    "popularity": random.randint(10, 100),
                },
            },
        }

        eventos.append(evento)

    return eventos


# =============================================================
# GENERACION DE ESCENARIOS
# =============================================================

def generar_escenarios(
    n: int = 30,
    seed: int | None = 43,
) -> list[dict[str, Any]]:
    """
    Genera escenarios de busqueda con ventanas de 1 a 3 meses.
    """
    if seed is not None:
        random.seed(seed)

    escenarios: list[dict[str, Any]] = []
    base_date = datetime.now(timezone.utc)

    for i in range(n):
        ciudad = random.choice(list(CIUDADES_DEMO.keys()))
        cats = random.sample(CATEGORIAS, k=random.randint(1, 3))

        # Ventana realista: 21 a 60 dias
        dias_inicio = random.randint(0, 7)
        dias_duracion = random.randint(21, 60)

        start = base_date + timedelta(days=dias_inicio)
        end = start + timedelta(days=dias_duracion)

        escenarios.append({
            "id": f"scenario_{i:04d}",
            "location": ciudad,
            "categories": cats,
            "duracion_maxima": random.choice([120, 180, 240]),
            "available_dates": (start.isoformat(), end.isoformat()),
            "velocidad_kmh": 30,
            "num_eventos": settings.default_agenda_size,
        })

    return escenarios


# =============================================================
# PERFILES DE USUARIO
# =============================================================

PerfilUsuario = Literal[
    "joven_fiestero",
    "familia",
    "turista_cultural",
    "profesional_tech",
    "deportista",
    "bohemio",
]

PERFILES: dict[str, dict[str, Any]] = {
    "joven_fiestero": {
        "categories": ["concerts", "festivals"],
        "velocidad_kmh": 40,
        "duracion_maxima": 300,
        "prefiere_noche": True,
    },
    "familia": {
        "categories": ["theater", "arts", "festivals"],
        "velocidad_kmh": 25,
        "duracion_maxima": 120,
        "prefiere_noche": False,
    },
    "turista_cultural": {
        "categories": ["arts", "theater", "literature"],
        "velocidad_kmh": 20,
        "duracion_maxima": 180,
        "prefiere_noche": False,
    },
    "profesional_tech": {
        "categories": ["technology", "conferences"],
        "velocidad_kmh": 35,
        "duracion_maxima": 240,
        "prefiere_noche": False,
    },
    "deportista": {
        "categories": ["sports", "wellness"],
        "velocidad_kmh": 30,
        "duracion_maxima": 180,
        "prefiere_noche": False,
    },
    "bohemio": {
        "categories": ["literature", "arts", "food"],
        "velocidad_kmh": 15,
        "duracion_maxima": 180,
        "prefiere_noche": True,
    },
}


def generar_perfiles_usuario() -> dict[str, dict[str, Any]]:
    return PERFILES.copy()


def simular_agenda_para_perfil(
    perfil: str,
    eventos: list[dict[str, Any]],
    seed: int | None = None,
) -> list[dict[str, Any]]:
    if perfil not in PERFILES:
        raise ValueError(f"Perfil desconocido: {perfil}. Validos: {list(PERFILES)}")

    if seed is not None:
        random.seed(seed)

    prefs = PERFILES[perfil]
    candidatos = [
        e for e in eventos
        if e["classification"]["primary_category"] in prefs["categories"]
    ]

    if not candidatos:
        return []

    k = min(settings.default_agenda_size, len(candidatos))
    return random.sample(candidatos, k=k)


# =============================================================
# MONTE CARLO
# =============================================================

def monte_carlo_runs(
    func,
    n_runs: int = 30,
    seeds: list[int] | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    if seeds is None:
        seeds = list(range(n_runs))

    if len(seeds) != n_runs:
        raise ValueError(f"Se esperaban {n_runs} seeds, se recibieron {len(seeds)}")

    resultados: list[dict[str, Any]] = []

    for seed in seeds:
        try:
            resultado = func(seed=seed, **kwargs)
            resultados.append({
                "seed": seed,
                "result": resultado,
                "status": "ok",
            })
        except Exception as e:
            resultados.append({
                "seed": seed,
                "result": None,
                "status": "error",
                "error": str(e),
            })

    return resultados


def resumen_monte_carlo(
    resultados: list[dict[str, Any]],
    extractor,
) -> dict[str, float]:
    import statistics

    valores = [
        extractor(r["result"])
        for r in resultados
        if r["status"] == "ok" and r["result"] is not None
    ]

    if not valores:
        return {"n_valid": 0}

    valores_ordenados = sorted(valores)
    n = len(valores_ordenados)

    return {
        "n_valid": n,
        "mean": statistics.mean(valores),
        "std": statistics.stdev(valores) if n > 1 else 0.0,
        "min": min(valores),
        "max": max(valores),
        "median": statistics.median(valores),
        "p25": valores_ordenados[int(0.25 * (n - 1))],
        "p75": valores_ordenados[int(0.75 * (n - 1))],
        "p90": valores_ordenados[int(0.90 * (n - 1))],
    }


# =============================================================
# HELPERS PRIVADOS
# =============================================================

def _hash_id(texto: str) -> str:
    return hashlib.md5(texto.encode()).hexdigest()[:8]


def _titulo_evento(categoria: str) -> str:
    titulos = {
        "concerts":    ["Concierto", "Gira", "Festival de musica"],
        "theater":     ["Obra", "Estreno teatral", "Comedia"],
        "sports":      ["Partido", "Final", "Torneo"],
        "arts":        ["Exposicion", "Muestra", "Instalacion"],
        "technology":  ["Conferencia", "Summit", "Taller"],
        "food":        ["Feria gastronomica", "Cata", "Festival culinario"],
        "literature":  ["Recital", "Lectura", "Encuentro literario"],
        "wellness":    ["Retiro", "Yoga", "Meditacion"],
        "festivals":   ["Festival", "Fiesta mayor", "Verbena"],
        "conferences": ["Congreso", "Simposio", "Jornada"],
    }
    return random.choice(titulos.get(categoria, ["Evento"]))


_REGIONES: dict[str, str] = {
    "Madrid": "Comunidad de Madrid", "Barcelona": "Cataluna",
    "Valencia": "Comunidad Valenciana", "Sevilla": "Andalucia",
    "Bilbao": "Pais Vasco", "Malaga": "Andalucia",
    "Zaragoza": "Aragon", "Granada": "Andalucia",
    "Palma": "Islas Baleares", "Ibiza": "Islas Baleares",
    "Paris": "Ile-de-France", "Berlin": "Berlin",
    "Rome": "Lazio", "London": "Greater London",
    "Amsterdam": "North Holland", "New York": "New York",
    "Mexico DF": "CDMX", "Buenos Aires": "CABA",
    "Bogota": "Cundinamarca", "La Habana": "La Habana",
    "Santiago": "Region Metropolitana", "Lima": "Lima",
    "Tokyo": "Tokyo", "Sydney": "New South Wales",
    "Singapore": "Singapore",
}

_PAISES: dict[str, str] = {
    "Madrid": "Spain", "Barcelona": "Spain", "Valencia": "Spain",
    "Sevilla": "Spain", "Bilbao": "Spain", "Malaga": "Spain",
    "Zaragoza": "Spain", "Granada": "Spain", "Palma": "Spain",
    "Ibiza": "Spain",
    "Paris": "France", "Berlin": "Germany", "Rome": "Italy",
    "London": "United Kingdom", "Amsterdam": "Netherlands",
    "New York": "United States", "Mexico DF": "Mexico",
    "Buenos Aires": "Argentina", "Bogota": "Colombia",
    "La Habana": "Cuba", "Santiago": "Chile", "Lima": "Peru",
    "Tokyo": "Japan", "Sydney": "Australia", "Singapore": "Singapore",
}


def _region_de(ciudad: str) -> str:
    return _REGIONES.get(ciudad, "Desconocida")


def _pais_de(ciudad: str) -> str:
    return _PAISES.get(ciudad, "Desconocido")
