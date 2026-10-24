<svg xmlns="http://www.w3.org/2000/svg" width="420" height="80" viewBox="0 0 420 80">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#1E90FF"/>
      <stop offset="55%" stop-color="#5B4BFF"/>
      <stop offset="100%" stop-color="#8A2BE2"/>
    </linearGradient>
  </defs>
  <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle"
        font-family="Segoe UI, Arial, sans-serif" font-size="48" font-weight="700"
        fill="url(#g)">🎫  Eventide</text>
</svg>

**Tu asistente personal de planes. Encuentra eventos, arma agendas, disfruta.**

---

## Que es Eventide?

Eventide es una aplicacion web que busca eventos culturales, deportivos y de ocio en multiples fuentes, los filtra segun tus gustos, y te arma una agenda personalizada con explicaciones en lenguaje natural.

Imagina decirle a una app:

> "Quiero hacer algo el sabado en Madrid, que sea de musica y no este muy lejos"

Y que te responda con un plan concreto:

> "Mira, te arme este plan:
> 21:00 - Concierto de Rosalia (Wizink Center)
> 23:30 - Festival Nocturno (Sala El Sol, a 5 min andando)
>
> Los dos eventos estan cerca, asi no pierdes tiempo en traslados.
> Categorias distintas para que la noche no sea monotona.
>
> Quieres que te reserve algo?"

**Eso es Eventide.**

---

## Que lo hace diferente?

| Otras apps | Eventide |
|---|---|
| Busqueda por palabras exactas | Busqueda semantica (entiende el significado) |
| Listado plano de eventos | Agenda optimizada (sin solapes, cerca) |
| Filtros rigidos | Recomendacion inteligente |
| Sin contexto | Narracion natural (te explica por que) |

**Tres tecnologias de vanguardia integradas:**

- IA: embeddings, grafos de conocimiento, LLMs.
- Optimizacion: Simulated Annealing para agendas.
- Busqueda semantica: FAISS para recuperacion ultrarrápida.

---

## Como usarlo

### 1. Clona el proyecto

    git clone https://github.com/usuario/eventide.git
    cd eventide

### 2. Instala dependencias

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"

### 3. Arranca la app

Terminal 1 (API):

    eventide serve

Terminal 2 (UI):

    streamlit run src/eventide/ui/app.py

Abre http://localhost:8501 en el navegador.

### 4. Empieza a buscar

Escribe lo que te apetece, elige filtros, y deja que Eventide haga el resto.

---

## Casos de uso

- Turistas: descubre que hacer en tu ciudad de destino.
- Locales: encuentra planes nuevos en tu ciudad.
- Grupos: organiza una noche completa sin solapes.
- Familias: busca eventos apropiados por categoria y duracion.

---

## Ventajas

- Busqueda por significado: encuentra eventos aunque no recuerdes el nombre exacto.
- Agenda optimizada: sin solapes, con venues cerca.
- Explicaciones humanas: entiendes por que te recomienda cada evento.
- Multiples fuentes: PredictHQ, SeatGeek, Ticketmaster.
- Gratis y open source.

---

## Limitaciones (honestas)

- Datos de demo: el sistema arranca con datos sinteticos. Con APIs reales necesita claves.
- Ciudades soportadas por defecto: Madrid, Barcelona, Valencia, Sevilla, Bilbao, Malaga, Palma, Zaragoza, Granada, Ibiza. Ampliable.
- Idioma: espanol neutro en la narracion.
- Narracion LLM: si no hay conexion, usa un fallback sin IA generativa.

---

## Resultados experimentales

- Modelo de embeddings elegido: NDCG@10 = 0.81 (mejor de 3 modelos evaluados).
- Algoritmo de optimizacion: Simulated Annealing gana a Hill Climbing y Random (p<0.001).
- Latencia end-to-end: aproximadamente 500 ms en mediana.
- Tests del sistema: mas de 135 tests automatizados.


### Comparación de modelos de embeddings

| Modelo | NDCG@10 | Precision@10 | Recall@10 | Latencia |
|---|---|---|---|---|
| **paraphrase-multilingual-mpnet-base-v2** | **0.8118** | **0.7300** | **0.6667** | 43.27ms |
| distiluse-base-multilingual-cased-v1 | 0.7849 | 0.7450 | 0.4500 | 22.32ms |
| all-MiniLM-L6-v2 | 0.5888 | 0.4800 | 0.4500 | 11.11ms |

El modelo elegido obtiene el mayor NDCG@10 y Recall@10 del experimento.

### Comparación de metaheurísticas

| Algoritmo | Media | Std | Min | Max |
|---|---|---|---|---|
| **Simulated Annealing** | **-21.44** | 14.09 | -45.43 | **+13.94** |
| Hill Climbing | -34.00 | 18.45 | -56.11 | +4.55 |
| Random Search | -91.86 | 18.86 | -123.57 | -58.60 |

SA supera a HC (p=0.0003, d=0.77) y a Random (p<0.001, d=4.27).

### Otros resultados

- Latencia end-to-end: ~500ms p50, ~1.1s p99.
- Tests del sistema: 135+ automatizados.

---

## Stack tecnico

Python 3.11, Flask, Streamlit, SentenceTransformers, FAISS, NetworkX, Gemini.

---

## Documentacion completa

- docs/IA.md: fundamentos de embeddings, grafos, LLMs.
- docs/SIMULACION.md: Simulated Annealing, estadistica, resultados.
- docs/SRI.md: recuperacion de informacion, NDCG, evaluacion.
- docs/INGENIERIA.md: arquitectura tecnica, como extenderlo.

---

## Autores

- Melani Forsythe Matos
- Olivia Ibanez Mustelier
- Orlando De La Torre Leal

Facultad de Matematica y Computacion, Universidad de La Habana, Cuba.

Licencia: MIT