# Conclusiones - Experimento 1: Embeddings

## Resultados

| Modelo | NDCG@10 | Precision@10 | Recall@10 | Latencia (ms) |
|---|---|---|---|---|
| `paraphrase-multilingual-mpnet-base-v2` | 0.8118 | 0.7300 | 0.6667 | 43.27 |
| `distiluse-base-multilingual-cased-v1` | 0.7849 | 0.7450 | 0.4500 | 22.32 |
| `all-MiniLM-L6-v2` | 0.5888 | 0.4800 | 0.4500 | 11.11 |

## Conclusion

El mejor modelo es **`paraphrase-multilingual-mpnet-base-v2`** con NDCG@10 = 0.8118.

**Justificacion:**

- Mayor NDCG@10 (calidad del ranking).
- Soporte multilingue.
- Latencia aceptable para uso interactivo.
