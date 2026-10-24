"""Demo interactiva del motor de búsqueda semántica."""

from eventide.core.embedding import EventEmbedder
from eventide.core.simulation import generar_eventos


def main():
    print("=" * 70)
    print("DEMO — Búsqueda semántica con Eventide")
    print("=" * 70)

    # 1. Cargar el modelo (singleton)
    EventEmbedder.reset()
    print("\n[1] Cargando modelo...")
    embedder = EventEmbedder()

    # 2. Generar 200 eventos sintéticos
    print("\n[2] Generando 200 eventos sintéticos...")
    eventos = generar_eventos(n=200, seed=42)

    # 3. Generar embeddings
    print("\n[3] Generando embeddings...")
    embedder.generate_embeddings(eventos)

    # 4. Construir índice FAISS + shards por ciudad
    print("\n[4] Construyendo índices...")
    embedder.build_index(index_type="flat")
    embedder.build_shards()

    print(f"\n   Total eventos: {embedder.num_events}")
    print(f"   Total shards:  {embedder.num_shards}")

    # 5. Probar varias queries
    queries = [
        "conciertos de música en Madrid",
        "exposiciones de arte en Barcelona",
        "partidos de fútbol",
        "conferencias de tecnología",
        "eventos gastronómicos en Valencia",
    ]

    for query in queries:
        print("\n" + "=" * 70)
        print(f"QUERY: {query}")
        print("=" * 70)

        resultados, scores = embedder.search(query, k=5)

        for r, s in zip(resultados, scores):
            title = r["basic_info"]["title"]
            city = r["spatial_info"]["area"]["city"]
            cat = r["classification"]["primary_category"]
            print(f"  {s:.3f} | {title}")
            print(f"          ciudad={city} | categoría={cat}")


if __name__ == "__main__":
    main()