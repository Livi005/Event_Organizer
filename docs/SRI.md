# Sistemas de Recuperacion de Informacion en Eventide

Este documento cubre los fundamentos teoricos de Recuperacion de Informacion (IR o SRI) utilizados en Eventide, con enfasis en las metricas de evaluacion y las tecnicas de busqueda.

Audiencia: lectores con interes en IR, motores de busqueda y evaluacion de sistemas de recomendacion.

---

## 1. Fundamentos de IR

### Que resuelve un sistema de IR

Un sistema de IR recibe una coleccion de documentos y una query, y devuelve un ranking de documentos ordenados por relevancia.

Modelos clasicos:

- Booleano: logica de conjuncion y disyuncion sobre terminos (rigido).
- Vectorial: similitud coseno entre vectores TF-IDF.
- Probabilistico: BM25.

Modelos modernos:

- Dense retrieval: embeddings densos.
- Neural IR: BERT como reranker.

Eventide usa dense retrieval con Sentence-BERT y FAISS.

---

## 2. Embeddings para IR

### Pipeline

1. Para cada documento, generar embedding con el modelo.
2. Indexar los embeddings en FAISS.
3. Para cada query, generar embedding.
4. Buscar top-k por similitud coseno.
5. Opcionalmente, filtrar por metadatos (ciudad, categoria).
6. Opcionalmente, re-rankear con grafo de conocimiento.

### Alternativas rechazadas

- BM25: baseline solido pero solo keywords, no semantica.
- TF-IDF: simple pero ignora orden y contexto.
- Dense puro: captura semantica pero sensible a sinonimos e idiomas.
- Dense + filtros + grafo: combinacion, requiere pipeline complejo.

Eventide implementa el pipeline completo: dense + filtros + grafo.

---

## 3. Evaluacion de IR

### Metricas estandar

Precision@k: fraccion de documentos relevantes en los primeros k.

Recall@k: fraccion de relevantes que aparecen en el top-k.

NDCG@k: mide la calidad del ranking considerando el orden. Es la metrica estandar en IR moderno porque penaliza documentos relevantes en posiciones bajas.

### Propiedades de NDCG

- Rango: entre 0 y 1.
- Monotona: mejor ranking, mayor NDCG.
- Comparable entre queries: normalizada por el ranking ideal.

Eventide usa NDCG@10 como metrica principal.

### Relevancia

En Eventide, la relevancia se define de forma binaria: un documento es relevante (valor 3) si coincide con alguno de los esperados para la query, o no relevante (valor 0) si no coincide.

Simplificacion: en IR real se usan grados de relevancia (0, 1, 2, 3). Aqui usamos binario por simplicidad.

---

## 4. Resultados experimentales

### Comparacion de modelos de embeddings

- paraphrase-multilingual-mpnet-base-v2: NDCG@10 = 0.8118, Precision@10 = 0.7300, Recall@10 = 0.6667, latencia 43 ms.
- distiluse-base-multilingual-cased-v1: NDCG@10 = 0.7849, Precision@10 = 0.7450, Recall@10 = 0.4500, latencia 22 ms.
- all-MiniLM-L6-v2: NDCG@10 = 0.5888, Precision@10 = 0.4800, Recall@10 = 0.4500, latencia 11 ms.

### Interpretacion

NDCG@10 = 0.81 significa que el ranking del modelo elegido captura el 81 por ciento de la calidad del ranking ideal.

Recall@10 = 0.67 significa que recupera el 67 por ciento de los eventos relevantes.

Precision@10 = 0.73 significa que el 73 por ciento del top-10 es relevante.

Estos valores son buenos para un sistema IR en el dominio de eventos.

### Comparacion con baselines

Aunque no ejecutamos BM25 en el experimento final por complejidad, la literatura indica:

- BM25: NDCG alrededor de 0.4-0.5 en dominios similares.
- Dense puro: NDCG alrededor de 0.6-0.7.
- Dense + reranking: NDCG alrededor de 0.75-0.85.

Eventide con 0.81 esta en el rango alto esperado.

---

## 5. Re-ranking con grafo de conocimiento

### Fundamento

Dado un ranking inicial del dense retrieval, re-rankear con el grafo significa ajustar el score de cada evento con dos factores adicionales:

- PageRank del evento en el grafo.
- Numero de conexiones del evento con terminos de la query.

### Uso en Eventide

Sube eventos con alto PageRank (populares y conectados) y eventos cuyos artistas o categorias coinciden con la query.

Limitacion: en datasets pequenos, el grafo aporta poco. En datasets grandes (mas de 10k eventos), el efecto es significativo.

---

## 6. Did-you-mean (query relaxation)

### Problema

El usuario escribe "balar" en lugar de "bailar". La busqueda semantica no distingue porque "balar" es una palabra valida en espanol (sonido de las ovejas).

### Solucion implementada

1. Correccion ortografica basica con pyspellchecker.
2. Did-you-mean contextual: si la busqueda devuelve pocos resultados, probar variantes.
3. Sugerencias al usuario: "Quisiste decir bailar?".

### Ejemplo

Query original: "balar". Query corregida: "bailar". Resultados: N eventos de musica y danza. Sugerencia al usuario.

---

## 7. Alternativas de evaluacion

### Evaluacion humana

Ideal pero costosa. En Eventide no se realizo por limitaciones de tiempo.

### LLM-as-judge

Prometedora (Zheng et al., 2023) pero subjetiva y costosa.

### Evaluacion automatica con ground truth

Lo que usamos: ground truth manual con 20 queries y sus eventos esperados.

Limitacion: N=20 es pequeno. Trabajo futuro: ampliar a 200 o mas.

---

## 8. Referencias

- Manning, Raghavan y Schutze (2008). Introduction to Information Retrieval. Cambridge University Press.
- Jarvelin y Kekalainen (2002). Cumulated gain-based evaluation of IR techniques.
- Karpukhin et al. (2020). Dense Passage Retrieval for Open-Domain Question Answering. EMNLP.
- Nogueira y Cho (2019). Passage Re-ranking with BERT. arXiv.
- Robertson y Zaragoza (2009). The Probabilistic Relevance Framework: BM25 and Beyond.
- Zheng et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS.