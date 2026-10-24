"""Prueba end-to-end de la API: buscar → optimizar → narrar."""

import json
import os
import sys
import time

# CRÍTICO: ignorar el proxy para localhost (red corporativa)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(var, None)

import requests  # noqa: E402

BASE = "http://localhost:8502"


def esperar_api_lista(timeout: int = 90) -> bool:
    print("⏳ Esperando a que la API esté lista...")
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            r = requests.get(f"{BASE}/health", timeout=10)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if data.get("status") == "healthy":
                        print(f"✅ API lista tras {time.time() - inicio:.1f}s")
                        return True
                except json.JSONDecodeError:
                    pass
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    print(f"❌ Timeout esperando API ({timeout}s)")
    return False


def main():
    print("=" * 70)
    print("TEST API — Flujo completo: buscar → optimizar → narrar")
    print("=" * 70)

    if not esperar_api_lista():
        return 1

    # ------------------------------------------------------------------
    # [1] Health
    # ------------------------------------------------------------------
    print("\n[1] Health check...")
    r = requests.get(f"{BASE}/health", timeout=10)
    health = r.json()
    print(f"    Status: {health['status']}")
    print(f"    Agentes: {health['agentes_registrados']}")

    # ------------------------------------------------------------------
    # [2] Ciudades
    # ------------------------------------------------------------------
    print("\n[2] Ciudades disponibles...")
    r = requests.get(f"{BASE}/api/v1/ciudades", timeout=10)
    ciudades = r.json().get("ciudades", [])
    print(f"    {len(ciudades)} ciudades: {ciudades[:5]}")

    # ------------------------------------------------------------------
    # [3] BUSCAR — con filtro de ciudad obligatorio
    # ------------------------------------------------------------------
    print("\n[3] Buscando 'concierto' en Madrid...")
    payload_buscar = {
        "query": "concierto",
        "ciudad": "Madrid",   # ← IMPRESCINDIBLE
        "k": 20,
    }
    print(f"    Payload: {json.dumps(payload_buscar, ensure_ascii=False)}")

    r = requests.post(
        f"{BASE}/api/v1/buscar",
        json=payload_buscar,
        timeout=30,
    )
    data = r.json()
    print(f"    Encontrados: {data['total']} eventos")
    for ev in data["resultados"][:5]:
        title = ev["basic_info"]["title"]
        city = ev["spatial_info"]["area"]["city"]
        start = ev["temporal_info"]["start"]
        print(f"      • [{start}] {title} ({city})")

    if data["total"] == 0:
        print("    ❌ No hay eventos. Abortando.")
        return 1

    # ------------------------------------------------------------------
    # [4] OPTIMIZAR
    # ------------------------------------------------------------------
    print("\n[4] Generando agenda óptima (SA)...")
    prefs = {
        "location": "Madrid",
        "categories": ["concerts", "festivals"],
        "available_dates": (
            "2025-01-01T00:00:00+00:00",
            "2027-12-31T00:00:00+00:00",
        ),
        "duracion_maxima": 240,
        "velocidad_kmh": 30,
    }
    r = requests.post(
        f"{BASE}/api/v1/agenda",
        json={
            "pool": data["resultados"],
            "preferencias": prefs,
            "cantidad": 5,
            "algoritmo": "sa",
            "seed": 42,
        },
        timeout=60,
    )
    agenda_data = r.json()
    agenda = agenda_data["agenda"]
    print(f"    Score: {agenda_data['score']:.2f}")
    print(f"    Algoritmo: {agenda_data['algoritmo']}")
    print(f"    Tiempo: {agenda_data['tiempo_ms']:.1f} ms")

    print("    Agenda (ordenada por fecha):")
    for ev in sorted(agenda, key=lambda e: str(e["temporal_info"].get("start") or "")):
        title = ev["basic_info"]["title"]
        city = ev["spatial_info"]["area"]["city"]
        start = ev["temporal_info"]["start"]
        print(f"      • [{start}] {title} ({city})")

    # ------------------------------------------------------------------
    # [5] NARRAR
    # ------------------------------------------------------------------
    print("\n[5] Generando narración...")
    r = requests.post(
        f"{BASE}/api/v1/narrar",
        json={
            "agenda": agenda,
            "preferencias": prefs,
            "query_original": "concierto en Madrid",
        },
        timeout=60,
    )
    narr = r.json()
    print(f"    Fuente: {narr['fuente']}")
    print(f"    Tiempo: {narr['tiempo_ms']} ms")
    print("\n" + "─" * 70)
    print(narr["texto"])
    print("─" * 70)

    print("\n✅ Flujo completo OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())