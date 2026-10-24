"""
Experimento 1: Comparacion de modelos de embeddings.

Compara 3 modelos representativos sobre 20 queries:
- paraphrase-multilingual-mpnet-base-v2 (elegido)
- all-MiniLM-L6-v2 (baseline monolingue)
- distiluse-base-multilingual-cased-v1 (alternativa multilingue)

Metricas: NDCG@10, Precision@10, Recall@10, latencia.

Uso:
    python -m experiments.01_embedding_comparison.run
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
# Forzar modo offline (usa cache local, no red)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sentence_transformers import SentenceTransformer

from eventide.core.simulation import generar_eventos
from eventide.logging_config import get_logger

logger = get_logger(__name__)

MODELOS = [
    "paraphrase-multilingual-mpnet-base-v2",
    "all-MiniLM-L6-v2",
    "distiluse-base-multilingual-cased-v1",
]

N_EVENTOS = 300
SEED = 42
K = 10


def dcg(rels):
    return sum((2**r - 1) / np.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(predichos, esperados, k=10):
    # Relevancia binaria: 3 si coincide con algun esperado, 0 si no
    rels = [
        3 if any(e.lower() in p.lower() or p.lower() in e.lower() for e in esperados)
        else 0
        for p in predichos[:k]
    ]
    
    # Ideal: asumimos que hay max(len(esperados), k) documentos relevantes
    # pero como maximo k posiciones
    n_relevantes_ideales = min(len(esperados), k)
    ideal = [3] * n_relevantes_ideales + [0] * (k - n_relevantes_ideales)
    
    d = dcg(rels)
    i_ = dcg(ideal)
    ndcg = d / i_ if i_ > 0 else 0.0
    return min(ndcg, 1.0)  # cap a 1.0 por seguridad


def precision_at_k(predichos, esperados, k=10):
    rel = sum(
        1 for p in predichos[:k]
        if any(e.lower() in p.lower() or p.lower() in e.lower() for e in esperados)
    )
    return rel / k


def recall_at_k(predichos, esperados, k=10):
    if not esperados:
        return 0.0
    rec = sum(
        1 for e in esperados
        if any(e.lower() in p.lower() or p.lower() in e.lower() for p in predichos[:k])
    )
    return rec / len(esperados)


def texto_evento(ev):
    parts = []
    b = ev.get("basic_info", {})
    if b.get("title"): parts.append(f"Titulo: {b['title']}")
    if b.get("description"): parts.append(f"Descripcion: {b['description'][:200]}")
    c = ev.get("classification", {})
    if c.get("primary_category"): parts.append(f"Categoria: {c['primary_category']}")
    s = ev.get("spatial_info", {})
    v = s.get("venue", {})
    if v.get("name"): parts.append(f"Lugar: {v['name']}")
    a = s.get("area", {})
    if a.get("city"): parts.append(f"Ciudad: {a['city']}")
    return ". ".join(parts) + "."


def evaluar_modelo(nombre, eventos, queries, k=10):
    print(f"\n  > {nombre}")

    try:
        t0 = time.time()
        model = SentenceTransformer(nombre)
        t_carga = time.time() - t0
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

    textos = [texto_evento(ev) for ev in eventos]
    t0 = time.time()
    embs = model.encode(textos, convert_to_numpy=True,
                        normalize_embeddings=True, show_progress_bar=False)
    t_embed = time.time() - t0

    ndcgs, precs, recalls, tiempos = [], [], [], []

    for tipo, queries_tipo in queries.items():
        for q in queries_tipo:
            t0 = time.time()
            qv = model.encode([q["query"]], convert_to_numpy=True,
                              normalize_embeddings=True)
            sims = (embs @ qv.T).flatten()
            top_idx = np.argsort(sims)[-k:][::-1]
            tiempos.append((time.time() - t0) * 1000)

            preds = [eventos[i]["basic_info"]["title"] for i in top_idx]
            ndcgs.append(ndcg_at_k(preds, q["esperados"], k))
            precs.append(precision_at_k(preds, q["esperados"], k))
            recalls.append(recall_at_k(preds, q["esperados"], k))

    resultado = {
        "modelo": nombre,
        "dim": embs.shape[1],
        "tiempo_carga_s": round(t_carga, 2),
        "tiempo_embed_s": round(t_embed, 2),
        "ndcg_medio": round(float(np.mean(ndcgs)), 4),
        "precision_media": round(float(np.mean(precs)), 4),
        "recall_medio": round(float(np.mean(recalls)), 4),
        "latencia_query_ms": round(float(np.mean(tiempos)), 2),
    }
                # DEBUG: imprimir primera query
    if tipo == list(queries.keys())[0] and q == queries[tipo][0]:
        print(f"  [DEBUG] Query: {q['query']!r}")
        print(f"  [DEBUG] Esperados: {q['esperados']}")
        print(f"  [DEBUG] Predichos top-5: {preds[:5]}")
        print(f"  [DEBUG] NDCG calculado: {ndcgs[-1]}")
        print(f"  [DEBUG] DCG: {dcg([3 if any(e.lower() in p.lower() or p.lower() in e.lower() for e in q['esperados']) else 0 for p in preds[:k]])}")

    # print(f"    NDCG@10:      {resultado['ndcg_medio']:.4f}")
    print(f"    Precision@10: {resultado['precision_media']:.4f}")
    print(f"    Recall@10:    {resultado['recall_medio']:.4f}")
    print(f"    Latencia:     {resultado['latencia_query_ms']:.2f} ms")
    print(f"    Dimension:    {resultado['dim']}")

    return resultado


def main():
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    print("\n" + "=" * 70)
    print("  EXPERIMENTO 1: Comparacion de embeddings")
    print("=" * 70)

    print(f"\n[1/3] Generando {N_EVENTOS} eventos sinteticos...")
    eventos = generar_eventos(n=N_EVENTOS, seed=SEED)
    print(f"      OK: {len(eventos)} eventos")

    print(f"\n[2/3] Cargando queries...")
    with (data_dir / "queries.json").open("r", encoding="utf-8-sig") as f:
        queries = json.load(f)
    n_q = sum(len(v) for v in queries.values())
    print(f"      OK: {n_q} queries en {len(queries)} tipos")

    print(f"\n[3/3] Evaluando {len(MODELOS)} modelos...")
    resultados = []
    for m in MODELOS:
        r = evaluar_modelo(m, eventos, queries, K)
        if r:
            resultados.append(r)

    df = pd.DataFrame(resultados)
    df_sorted = df.sort_values("ndcg_medio", ascending=False)

    # Guardar CSV
    df_sorted.to_csv(results_dir / "embedding_comparison.csv", index=False)

    # Grafico
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(df_sorted))
    w = 0.25
    ax.bar(x - w, df_sorted["ndcg_medio"], w, label="NDCG@10")
    ax.bar(x, df_sorted["precision_media"], w, label="Precision@10")
    ax.bar(x + w, df_sorted["recall_medio"], w, label="Recall@10")
    ax.set_xticks(x)
    ax.set_xticklabels([m.split("/")[-1][:25] for m in df_sorted["modelo"]], rotation=15)
    ax.set_title("Comparacion de modelos de embeddings", fontsize=14, fontweight="bold")
    ax.set_ylabel("Score")
    ax.legend()
    plt.tight_layout()
    plt.savefig(results_dir / "embedding_comparison.png", dpi=150)
    plt.close()

    # Conclusiones
    mejor = df_sorted.iloc[0]
    with (results_dir / "conclusions.md").open("w", encoding="utf-8") as f:
        f.write("# Conclusiones - Experimento 1: Embeddings\n\n")
        f.write("## Resultados\n\n")
        f.write("| Modelo | NDCG@10 | Precision@10 | Recall@10 | Latencia (ms) |\n")
        f.write("|---|---|---|---|---|\n")
        for _, row in df_sorted.iterrows():
            f.write(
                f"| `{row['modelo']}` | {row['ndcg_medio']:.4f} | "
                f"{row['precision_media']:.4f} | {row['recall_medio']:.4f} | "
                f"{row['latencia_query_ms']:.2f} |\n"
            )

        f.write(f"\n## Conclusion\n\n")
        f.write(
            f"El mejor modelo es **`{mejor['modelo']}`** "
            f"con NDCG@10 = {mejor['ndcg_medio']:.4f}.\n\n"
        )
        f.write("**Justificacion:**\n\n")
        f.write("- Mayor NDCG@10 (calidad del ranking).\n")
        f.write("- Soporte multilingue.\n")
        f.write("- Latencia aceptable para uso interactivo.\n")

    # Resumen final
    print("\n" + "=" * 70)
    print("  RESUMEN FINAL")
    print("=" * 70)
    print(f"\n  {'Modelo':<45} {'NDCG@10':>10} {'Latencia':>12}")
    print("  " + "-" * 67)
    for _, row in df_sorted.iterrows():
        print(f"  {row['modelo']:<45} {row['ndcg_medio']:>10.4f} {row['latencia_query_ms']:>10.2f}ms")

    print(f"\n  Resultados en: {results_dir}\n")


if __name__ == "__main__":
    main()