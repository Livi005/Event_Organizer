"""Demo del narrador con Gemini (o fallback)."""

import time

from loguru import logger

# Silenciar logs de librerías ruidosas
logger.remove()
logger.add(lambda msg: None, level="WARNING")

from eventide.agents.base import BuzonGlobal
from eventide.agents.narrador import AgenteNarrador
from eventide.core.embedding import EventEmbedder
from eventide.core.optimizer import optimizar_agenda
from eventide.core.simulation import generar_eventos


def main():
    print("=" * 70)
    print("DEMO — Narrador con Gemini")
    print("=" * 70)

    # 1. Cargar índice de embeddings
    print("\n[1] Cargando índice de embeddings...")
    EventEmbedder.reset()
    BuzonGlobal.limpiar()

    embedder = EventEmbedder()
    eventos_todos = generar_eventos(n=200, seed=42)
    embedder.generate_embeddings(eventos_todos)
    embedder.build_index(index_type="flat")
    embedder.build_shards()

    # 2. Buscar SOLO eventos en Madrid
    print("\n[2] Buscando 'concierto' en Madrid...")
    preferencias = {
        "location": "Madrid",
        "categories": ["concerts", "festivals"],
        "available_dates": (
            "2025-01-01T00:00:00+00:00",
            "2027-12-31T00:00:00+00:00",
        ),
        "duracion_maxima": 240,
        "velocidad_kmh": 30,
    }

    resultados, _ = embedder.filtered_search(
        query="concierto",
        city="Madrid",
        category=None,
        fecha_inicio=None,
        fecha_fin=None,
        k=20,
    )
    print(f"    Encontrados: {len(resultados)} eventos en Madrid")

    if not resultados:
        print("    ⚠️ Sin resultados. Usando todos los eventos.")
        resultados = eventos_todos[:20]

    # 3. Generar agenda
    print("\n[3] Generando agenda óptima (SA)...")
    agenda, score, _ = optimizar_agenda(
        resultados,
        preferencias,
        cantidad=min(5, len(resultados)),
        algoritmo="sa",
        seed=42,
    )
    print(f"    Score: {score:.2f}")
    print("    Agenda:")
    for ev in sorted(agenda, key=lambda e: str(e["temporal_info"].get("start") or "")):
        title = ev["basic_info"]["title"]
        city = ev["spatial_info"]["area"]["city"]
        print(f"      • {title} ({city})")

    # 4. Lanzar narrador
    print("\n[4] Lanzando narrador...")
    narrador = AgenteNarrador(nombre="narrador", usar_llm=True)
    narrador.start()
    time.sleep(2.0)

    # 5. Pedir narración
    print("\n[5] Pidiendo narración...")
    from queue import Queue

    bandeja_cliente = Queue()
    BuzonGlobal.registrar("cliente_demo", bandeja_cliente)

    narrador.enviar(
        "narrador", "narrar",
        {
            "agenda": agenda,
            "preferencias": preferencias,
            "query_original": "planes para el sábado en Madrid",
            "respuesta_a": "cliente_demo",
        },
    )

    try:
        respuesta = bandeja_cliente.get(timeout=30)
        print("\n" + "=" * 70)
        print("NARRACIÓN GENERADA")
        print("=" * 70)
        print(respuesta.payload["texto"])
        print("\n" + "-" * 70)
        print(f"Fuente: {respuesta.payload['fuente']}")
        print(f"Tiempo: {respuesta.payload['tiempo_ms']} ms")
    except Exception as e:
        print(f"❌ Error: {e}")

    narrador.stop()
    EventEmbedder.reset()


if __name__ == "__main__":
    main()