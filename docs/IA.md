# Inteligencia Artificial en Eventide

Este documento explica los fundamentos teoricos de IA utilizados en Eventide: por que cada tecnica, que alternativas se consideraron, y que evidencia experimental justifica la eleccion.

Audiencia: lectores con interes academico en IA, NLP y representacion del conocimiento.

---

## 1. Representacion semantica con embeddings

### Que es un embedding

Un embedding es una funcion que mapea un texto a un vector denso en un espacio de alta dimension. La propiedad clave es que textos con significado similar quedan cerca en ese espacio.

Formalmente, un modelo de embeddings aprende una funcion f: Texto -> R^n de manera que la similitud entre f(a) y f(b) aproxima la similitud semantica entre a y b. La similitud se mide normalmente con similitud coseno.

### Modelos evaluados

Comparamos 3 modelos representativos de Sentence-BERT:

- paraphrase-multilingual-mpnet-base-v2 (768 dimensiones, 50+ idiomas).
- distiluse-base-multilingual-cased-v1 (512 dimensiones, 50+ idiomas).
- all-MiniLM-L6-v2 (384 dimensiones, solo ingles).

Alternativas rechazadas:

- Modelos monolingues como all-mpnet-base-v2: descartados por falta de soporte para eventos en idiomas no ingleses.
- Modelos gigantes como e5-mistral-7b: descartados por coste computacional.
- TF-IDF y BM25: baseline clasico, pero no captura semantica.

### Justificacion de la eleccion

Resultados experimentales sobre 300 eventos y 20 queries:

- paraphrase-multilingual-mpnet-base-v2: NDCG@10 = 0.8118, Precision@10 = 0.7300, Recall@10 = 0.6667, latencia 43 ms.
- distiluse-base-multilingual-cased-v1: NDCG@10 = 0.7849, Precision@10 = 0.7450, Recall@10 = 0.4500, latencia 22 ms.
- all-MiniLM-L6-v2: NDCG@10 = 0.5888, Precision@10 = 0.4800, Recall@10 = 0.4500, latencia 11 ms.

Conclusion: el modelo elegido obtiene el mayor NDCG@10 y Recall@10. Aunque all-MiniLM-L6-v2 es 4 veces mas rapido, su calidad es 28 por ciento peor. distiluse es un buen compromiso pero su Recall es 22 por ciento inferior.

---

## 2. Busqueda vectorial con FAISS

### El problema

Dado un conjunto de N embeddings y una query, el problema es encontrar los K mas similares. Para N grande, el escaneo lineal es demasiado lento.

### Alternativas evaluadas

- Indice Flat (exacto): complejidad O(N), memoria minima. Ideal para N menor que 100k.
- HNSW (grafo): complejidad O(log N), 5 veces mas memoria. Ideal para N mayor que 500k.
- IVFFlat (clustering): complejidad O(sqrt(N)), requiere entrenamiento previo.

### Justificacion

Con N entre 300 y 2000 eventos, el indice Flat es suficiente (aproximadamente 50 ms por query). Ademas:

- No tiene parametros que ajustar.
- Es 100 por ciento exacto.
- Combinado con sharding por ciudad, reduce el espacio efectivo.

Migracion futura: si el corpus crece a mas de 500k eventos, migraremos a HNSW.

---

## 3. Grafos de conocimiento

### Que es un grafo de conocimiento

Un grafo de conocimiento es una estructura de nodos y aristas donde los nodos representan entidades y las aristas representan relaciones tipadas.

Eventide construye un grafo con NetworkX donde cada evento se conecta a:

- Su ciudad.
- Su categoria.
- Sus artistas.
- Otros eventos similares (con similitud coseno mayor a 0.88).

### PageRank para re-ranking

El algoritmo PageRank mide la importancia de un nodo en funcion de sus conexiones entrantes. Los eventos con mayor PageRank son mas centrales en el grafo.

Uso en Eventide: los eventos con alto PageRank se usan como bonus en el ranking final.

### Alternativas rechazadas

- Solo embeddings: no captura relaciones explicitas.
- RDF y OWL: mas expresivos pero excesivamente complejos para este dominio.
- GraphRAG de Microsoft 2024: interesante pero requiere LLMs locales viables.

### Justificacion

El grafo aporta:

1. Razonamiento explicito, como "artistas que actuan en ciudades donde tambien toca X".
2. Re-ranking informado, subiendo eventos conectados con artistas o categorias populares.
3. Base para futuras extensiones (GraphRAG-ready).

---

## 4. Modelos de lenguaje para narracion

### Que es un LLM

Un Large Language Model es un modelo autoregresivo entrenado para predecir el siguiente token. Dado un prompt, genera una secuencia de texto coherente.

Uso en Eventide: generar una explicacion en lenguaje natural de la agenda recomendada.

### Modelos considerados

- Gemini 1.5 Flash: rapido, gratuito en su tier, buena calidad. Requiere API key.
- GPT-4: excelente calidad pero costoso por token.
- LLaMA 3 local: sin coste API, privacidad. Requiere GPU, mas lento.
- Fallback local: sin dependencias, calidad muy inferior.

### Justificacion

Gemini Flash ofrece latencia aceptable (aproximadamente 2 segundos por narracion), buena calidad en espanol, y free tier generoso.

Fallback: si el LLM falla o tarda mas de 8 segundos, se usa una narracion plantilla (menos natural pero funcional).

### Filtros de sensatez

Antes de pasar datos al LLM, se filtran:

- Distancias mayores a 30 km: no se mencionan.
- Huecos mayores a 24 horas: no se mencionan.
- Datos absurdos: descartados.

Objetivo: reducir alucinaciones y evitar narrativas raras.

---

## 5. Arquitectura neuro-simbolica

Eventide combina dos paradigmas de IA:

- Subsimbolico: embeddings (redes neuronales).
- Simbolico: grafo de conocimiento (logica explicita).

Ventaja: los embeddings capturan semantica difusa; el grafo captura relaciones explicitas. Juntos son mas potentes que cada uno por separado.

---

## 6. Referencias

- Reimers y Gurevych (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP.
- Johnson, Douze y Jegou (2019). Billion-scale similarity search with GPUs. IEEE Transactions on Big Data.
- Page, Brin, Motwani y Winograd (1999). The PageRank Citation Ranking. Stanford InfoLab.
- Lewis et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.