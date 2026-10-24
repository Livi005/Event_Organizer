"""Demo del grafo de conocimiento."""

from loguru import logger

logger.remove()

from eventide.core.embedding import EventEmbedder
from eventide.core.knowledge_graph import KnowledgeGraph
from eventide.core.simulation import generar_eventos


def main():
    print("=" * 70)
    print("DEMO — Grafo de conocimiento neuro-simbólico")
    print("=" * 70)

    eventos = generar_eventos(n=100, seed=42)

    # Construir grafo SIN similitud (rápido)
    print("\n[1] Construyendo grafo sin similitud semántica...")
    kg = KnowledgeGraph()
    kg.build(eventos, embedder=None)

    stats = kg.estadisticas()
    print(f"\n   Nodos:    {stats['num_nodos']}")
    print(f"   Aristas:  {stats['num_aristas']}")
    print("\n   Nodos por tipo:")
    for tipo, count in sorted(stats["nodos_por_tipo"].items(), key=lambda x: -x[1]):
        print(f"     {tipo:<20} {count}")
    print("\n   Aristas por tipo:")
    for tipo, count in sorted(stats["aristas_por_tipo"].items(), key=lambda x: -x[1]):
        print(f"     {tipo:<20} {count}")

    print("\n[2] Top 10 eventos por PageRank:")
    top = kg.top_eventos_por_pagerank(k=10)
    for i, (titulo, score) in enumerate(top, 1):
        print(f"   {i:>2}. {score:.5f}  {titulo}")

    print("\n[3] Enriquecer candidatos con query 'Madrid':")
    candidatos = eventos[:20]
    enriquecidos = kg.enriquecer(candidatos, "Madrid", k=5)
    for ev, score in enriquecidos:
        title = ev["basic_info"]["title"]
        city = ev["spatial_info"]["area"]["city"]
        print(f"   {score:>6.2f}  {title}  ({city})")


if __name__ == "__main__":
    main()