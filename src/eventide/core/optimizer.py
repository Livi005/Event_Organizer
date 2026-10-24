"""
Módulo de optimización combinatoria para generación de agendas.

Implementa:
- Función objetivo multi-criterio (evaluar_agenda)
- Simulated Annealing (metaheurística estocástica)
- Hill Climbing (búsqueda local)
- Random Search (baseline)

El problema: dado un pool de N eventos y preferencias del usuario,
seleccionar K eventos (K << N) que maximicen el score total sin
solapamiento temporal.

Uso:
    from eventide.core.optimizer import optimizar_agenda

    agenda, score, trace = optimizar_agenda(
        eventos, preferencias, cantidad=5, algoritmo="sa"
    )
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from geopy.distance import geodesic

from eventide.config import settings
from eventide.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================
# PESOS DE LA FUNCIÓN OBJETIVO
# =============================================================

PESOS: dict[str, float] = {
    # --- Premios por preferencias ---
    "categoria": 3.0,
    "ciudad": 2.5,
    "fecha": 2.0,
    "duracion": 1.0,
    "diversidad": 1.5,
    "grafo": 3.0,

    # --- Premios por compacidad (los nuevos) ---
    "proximidad_temporal": 2.0,   # premia eventos cercanos en tiempo
    "proximidad_geografica": 1.5, # premia eventos cercanos en espacio

    # --- Penalizaciones suaves (opcionales, pequeñas) ---
    "traslado": -0.01,
    "huecos": -0.5,
}

# =============================================================
# UTILIDADES DE FECHAS Y GEO
# =============================================================

def _ensure_aware(dt: datetime | str) -> datetime:
    """Convierte str/datetime naive a datetime UTC-aware."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _parse_start(event: dict[str, Any]) -> datetime | None:
    """Extrae la fecha de inicio de un evento como datetime aware."""
    raw = event.get("temporal_info", {}).get("start")
    if not raw:
        return None
    try:
        return _ensure_aware(raw)
    except (ValueError, AttributeError):
        return None


def _get_duration(event: dict[str, Any], default: int = 120) -> int:
    """Devuelve la duración en minutos (default 120)."""
    return event.get("temporal_info", {}).get("duration_minutes", default) or default


def _get_coords(event: dict[str, Any]) -> tuple[float, float] | None:
    """Devuelve (lat, lon) del venue, o None si no disponibles."""
    loc = event.get("spatial_info", {}).get("venue", {}).get("location", {})
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    if lat is None or lon is None:
        return None
    return (lat, lon)


def hay_solape(e1: dict[str, Any], e2: dict[str, Any]) -> bool:
    """True si dos eventos se solapan en el tiempo."""
    s1, s2 = _parse_start(e1), _parse_start(e2)
    if s1 is None or s2 is None:
        return False  # sin fecha => no se considera solape
    e1_end = s1 + timedelta(minutes=_get_duration(e1))
    e2_end = s2 + timedelta(minutes=_get_duration(e2))
    return not (e1_end <= s2 or e2_end <= s1)


def _tiempo_traslado_min(
    e1: dict[str, Any],
    e2: dict[str, Any],
    velocidad_kmh: float = 30.0,
) -> float:
    """Tiempo estimado de traslado entre dos eventos en minutos."""
    c1, c2 = _get_coords(e1), _get_coords(e2)
    if c1 is None or c2 is None:
        return 0.0
    distancia_km = geodesic(c1, c2).km
    return (distancia_km / velocidad_kmh) * 60.0


# =============================================================
# FUNCIÓN OBJETIVO
# =============================================================

def evaluar_agenda(
    agenda: list[dict[str, Any]],
    preferencias: dict[str, Any],
    scores_grafo: dict[str, float] | None = None,
) -> float:
    """
    Evalúa una agenda con premios por preferencias + premios por compacidad
    + penalizaciones suaves.

    Cambio de diseño respecto a versiones previas:
      - Los huecos y traslados ya no se penalizan fuerte.
      - En su lugar, se PREMIA la proximidad temporal y geográfica.
      - Resultado: scores centrados cerca de 0, con valores positivos
        cuando la agenda es coherente.

    Rango típico: [-50, +80] para 5 eventos.
    """
    if not agenda:
        return 0.0

    # --- Preferencias del usuario ---
    velocidad = preferencias.get("velocidad_kmh", 30)
    duracion_max = preferencias.get("duracion_maxima")
    cats_pref = set(preferencias.get("categories") or [])
    ciudad_pref = preferencias.get("location")
    fechas = preferencias.get("available_dates")

    score = 0.0
    categorias_vistas: set[str] = set()

    # ==========================================================
    # 1. Premios por evento individual
    # ==========================================================
    for ev in agenda:
        # Categoría
        cat = ev.get("classification", {}).get("primary_category", "")
        if cat and cat in cats_pref:
            score += PESOS["categoria"]
        categorias_vistas.add(cat)

        # Ciudad
        ciudad = ev.get("spatial_info", {}).get("area", {}).get("city", "")
        if ciudad_pref and ciudad == ciudad_pref:
            score += PESOS["ciudad"]

        # Fecha dentro del rango
        if fechas:
            start_event = _parse_start(ev)
            if start_event:
                try:
                    lo = _ensure_aware(fechas[0])
                    hi = _ensure_aware(fechas[1])
                    if lo <= start_event <= hi:
                        score += PESOS["fecha"]
                except (ValueError, TypeError):
                    pass

        # Duración
        dur = ev.get("temporal_info", {}).get("duration_minutes")
        if duracion_max and dur:
            if dur <= duracion_max:
                score += PESOS["duracion"]
            else:
                score -= PESOS["duracion"]

        # Bonus por PageRank
        if scores_grafo:
            titulo = ev.get("basic_info", {}).get("title", "")
            score += scores_grafo.get(titulo, 0.0) * PESOS["grafo"]

    # ==========================================================
    # 2. Premio por diversidad
    # ==========================================================
    score += len(categorias_vistas) * PESOS["diversidad"]

    # ==========================================================
    # 3. Premio por compacidad temporal
    #    Ordena los eventos por fecha; para cada par consecutivo,
    #    premia si están cerca en el tiempo.
    # ==========================================================
    ordenados = sorted(
        [e for e in agenda if _parse_start(e)],
        key=lambda e: _parse_start(e),
    )

    for i in range(len(ordenados) - 1):
        s1 = _parse_start(ordenados[i])
        s2 = _parse_start(ordenados[i + 1])
        if s1 and s2:
            gap_h = (s2 - s1).total_seconds() / 3600
            # Premio máximo si gap ≤ 24h, decae linealmente hasta 0 a 168h (7 días)
            if gap_h <= 168:
                premio = PESOS["proximidad_temporal"] * (1.0 - gap_h / 168.0)
                score += premio

    # ==========================================================
    # 4. Premio por compacidad geográfica
    #    Para pares consecutivos, premia si están a < 50 km.
    # ==========================================================
    for i in range(len(ordenados) - 1):
        c1 = _get_coords(ordenados[i])
        c2 = _get_coords(ordenados[i + 1])
        if c1 and c2:
            dist_km = geodesic(c1, c2).km
            if dist_km <= 50:
                premio = PESOS["proximidad_geografica"] * (1.0 - dist_km / 50.0)
                score += premio

    # ==========================================================
    # 5. Penalización suave por huecos (en horas promedio, capado)
    # ==========================================================
    score += _calcular_huecos(ordenados) * PESOS["huecos"]

    # ==========================================================
    # 6. Penalización suave por traslados extremos (> 2h de viaje)
    # ==========================================================
    for i in range(len(ordenados) - 1):
        t = _tiempo_traslado_min(ordenados[i], ordenados[i + 1], velocidad)
        if t > 120:
            score += (t - 120) * PESOS["traslado"]

    return score


def _calcular_huecos(agenda: list[dict[str, Any]], max_horas: float = 168.0) -> float:
    """
    Hueco promedio entre eventos consecutivos, capeado a `max_horas`.
    """
    if len(agenda) < 2:
        return 0.0

    intervalos: list[tuple[datetime, datetime]] = []
    for ev in agenda:
        s = _parse_start(ev)
        if s is None:
            continue
        e = s + timedelta(minutes=_get_duration(ev))
        intervalos.append((s, e))

    intervalos.sort(key=lambda x: x[0])

    huecos: list[float] = []
    for i in range(len(intervalos) - 1):
        diff_h = (intervalos[i + 1][0] - intervalos[i][1]).total_seconds() / 3600
        if diff_h > 0:
            huecos.append(min(diff_h, max_horas))

    if not huecos:
        return 0.0
    return sum(huecos) / len(huecos)


# =============================================================
# GENERACIÓN DE SOLUCIÓN INICIAL
# =============================================================

def _agenda_valida(agenda: list[dict[str, Any]]) -> bool:
    """True si no hay solapes entre pares de eventos."""
    for i in range(len(agenda)):
        for j in range(i + 1, len(agenda)):
            if hay_solape(agenda[i], agenda[j]):
                return False
    return True


def generar_solucion_inicial(
    pool: list[dict[str, Any]],
    n: int,
    rng: random.Random,
    estrategia: str = "greedy",
) -> list[dict[str, Any]]:
    """
    Genera una agenda inicial válida (sin solapes).

    Estrategias:
        - "greedy": ordena por fecha y añade los que no solapen.
        - "random": baraja el pool y añade aleatoriamente.
    """
    validos = [e for e in pool if _parse_start(e) is not None]
    if len(validos) < n:
        return validos[:]

    if estrategia == "greedy":
        ordenados = sorted(
            validos,
            key=lambda e: _parse_start(e) or datetime.max.replace(tzinfo=timezone.utc),
        )
    elif estrategia == "random":
        ordenados = validos.copy()
        rng.shuffle(ordenados)
    else:
        raise ValueError(f"Estrategia desconocida: {estrategia}")

    agenda: list[dict[str, Any]] = []
    for ev in ordenados:
        if len(agenda) >= n:
            break
        if not any(hay_solape(ev, x) for x in agenda):
            agenda.append(ev)

    # Si no llegamos a n, completar aleatoriamente
    intentos = 0
    while len(agenda) < n and intentos < 200:
        candidato = rng.choice(validos)
        if candidato not in agenda and not any(hay_solape(candidato, x) for x in agenda):
            agenda.append(candidato)
        intentos += 1

    return agenda[:n]

# =============================================================
# VECINDAD: genera una solución vecina válida
# =============================================================

def _generar_vecino(
    agenda: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    rng: random.Random,
    max_intentos: int = 50,
) -> list[dict[str, Any]]:
    """Reemplaza un evento aleatorio por otro que no produzca solapes."""
    if not agenda:
        return agenda

    vecino = agenda.copy()
    idx = rng.randrange(len(vecino))

    for _ in range(max_intentos):
        candidato = rng.choice(pool)
        if candidato in vecino:
            continue
        vecino[idx] = candidato
        if _agenda_valida(vecino):
            return vecino

    return agenda  # no se encontró vecino válido


# =============================================================
# ALGORITMOS
# =============================================================

def random_search(
    pool: list[dict[str, Any]],
    preferencias: dict[str, Any],
    n: int = 5,
    max_iter: int = 100,
    seed: int | None = None,
    scores_grafo: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], float, list[float]]:
    """Búsqueda aleatoria (baseline tonto)."""
    rng = random.Random(seed)

    mejor_score = -float("inf")
    mejor: list[dict[str, Any]] = []
    trace: list[float] = []

    # Evaluar la primera solución
    primera = generar_solucion_inicial(pool, n, rng, estrategia="random")
    mejor = primera
    mejor_score = evaluar_agenda(primera, preferencias, scores_grafo)
    trace.append(mejor_score)

    # Resto de iteraciones
    for _ in range(max_iter):
        candidato = generar_solucion_inicial(pool, n, rng, estrategia="random")
        s = evaluar_agenda(candidato, preferencias, scores_grafo)
        if s > mejor_score:
            mejor, mejor_score = candidato, s
        trace.append(mejor_score)

    return mejor, mejor_score, trace


def hill_climbing(
    pool: list[dict[str, Any]],
    preferencias: dict[str, Any],
    n: int = 5,
    max_iter: int = 100,
    seed: int | None = None,
    scores_grafo: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], float, list[float]]:
    """Hill Climbing (búsqueda local greedy)."""
    rng = random.Random(seed)
    actual = generar_solucion_inicial(pool, n, rng)
    actual_score = evaluar_agenda(actual, preferencias, scores_grafo)
    trace = [actual_score]

    for _ in range(max_iter):
        vecino = _generar_vecino(actual, pool, rng)
        s = evaluar_agenda(vecino, preferencias, scores_grafo)
        if s > actual_score:
            actual, actual_score = vecino, s
        trace.append(actual_score)

    return actual, actual_score, trace


def simulated_annealing(
    pool: list[dict[str, Any]],
    preferencias: dict[str, Any],
    n: int = 5,
    max_iter: int | None = None,
    T_ini: float | None = None,
    T_fin: float | None = None,
    seed: int | None = None,
    scores_grafo: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], float, list[float]]:
    """
    Simulated Annealing con schedule de enfriamiento geométrico.

    Acepta vecinos peores con probabilidad exp(ΔE / T), lo que permite
    escapar de óptimos locales al principio y refinar al final.
    """
    rng = random.Random(seed)
    max_iter = max_iter or settings.sa_max_iterations
    T_ini = T_ini if T_ini is not None else settings.sa_initial_temperature
    T_fin = T_fin if T_fin is not None else settings.sa_final_temperature

    actual = generar_solucion_inicial(pool, n, rng)
    actual_score = evaluar_agenda(actual, preferencias, scores_grafo)

    mejor = actual.copy()
    mejor_score = actual_score
    trace = [mejor_score]

    # Factor de enfriamiento geométrico
    alpha = (T_fin / T_ini) ** (1.0 / max(1, max_iter))
    T = T_ini

    for _ in range(max_iter):
        vecino = _generar_vecino(actual, pool, rng)
        vecino_score = evaluar_agenda(vecino, preferencias, scores_grafo)
        delta = vecino_score - actual_score

        # Criterio de Metropolis
        if delta > 0 or (T > 1e-9 and rng.random() < math.exp(delta / T)):
            actual, actual_score = vecino, vecino_score
            if vecino_score > mejor_score:
                mejor, mejor_score = vecino.copy(), vecino_score

        trace.append(mejor_score)
        T *= alpha

    return mejor, mejor_score, trace


# =============================================================
# API DE ALTO NIVEL
# =============================================================

ALGORITMOS: dict[str, Callable] = {
    "random": random_search,
    "hc": hill_climbing,
    "sa": simulated_annealing,
}


def optimizar_agenda(
    pool: list[dict[str, Any]],
    preferencias: dict[str, Any],
    cantidad: int | None = None,
    algoritmo: str = "sa",
    seed: int | None = None,
    scores_grafo: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], float, list[float]]:
    """
    Punto de entrada principal.

    Args:
        pool: lista de eventos candidatos.
        preferencias: dict con location, categories, available_dates,
                      duracion_maxima, velocidad_kmh.
        cantidad: tamaño de la agenda (default: settings.default_agenda_size).
        algoritmo: "sa", "hc", "random".
        seed: semilla para reproducibilidad.
        scores_grafo: dict {titulo: pagerank} opcional.

    Returns:
        (agenda, score, trace)
    """
    cantidad = cantidad or settings.default_agenda_size
    if len(pool) < cantidad:
        raise ValueError(
            f"Se necesitan al menos {cantidad} eventos, hay {len(pool)}"
        )

    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconocido: {algoritmo}. Válidos: {list(ALGORITMOS)}")

    logger.info(
        f"Optimizando agenda: algoritmo={algoritmo}, n={cantidad}, "
        f"pool={len(pool)}, seed={seed}"
    )

    return ALGORITMOS[algoritmo](
        pool, preferencias, n=cantidad,
        seed=seed, scores_grafo=scores_grafo,
    )