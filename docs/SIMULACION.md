# Simulacion y Optimizacion en Eventide

Este documento cubre los fundamentos de simulacion y optimizacion combinatoria utilizados en Eventide, con enfasis en la eleccion de Simulated Annealing y los resultados estadisticos experimentales.

Audiencia: lectores con interes en optimizacion, metaheuristicas y analisis estadistico.

---

## 1. El problema de optimizacion

### Formulacion informal

Dados N eventos candidatos, un conjunto de preferencias del usuario, y un tamano de agenda K, el problema es seleccionar K eventos que maximicen una funcion de calidad, sin que se solapen temporalmente.

Complejidad: el problema es NP-hard (variante del Knapsack bidimensional con restricciones temporales).

Para K=5 y N=2000, hay aproximadamente 2.65 x 10^13 combinaciones posibles. La evaluacion exhaustiva es inviable.

Solucion: metaheuristicas.

---

## 2. Funcion objetivo multi-criterio

### Definicion informal

El score de una agenda es una suma ponderada de factores positivos (premios) menos factores negativos (penalizaciones suaves).

Factores positivos:

- Categoria preferida del usuario.
- Ciudad preferida.
- Fecha dentro del rango solicitado.
- Duracion adecuada (menor que la maxima pedida).
- Diversidad de categorias (mas variedad, mejor).
- Proximidad temporal entre eventos.
- Proximidad geografica entre eventos.
- PageRank en el grafo de conocimiento.

Factores negativos:

- Traslados largos (mayores a 2 horas entre eventos).
- Huecos muertos entre eventos.

### Pesos calibrados

Los pesos se ajustaron experimentalmente para que premios y penalizaciones esten balanceados. La decision clave de diseno fue premiar antes que castigar: las versiones iniciales con solo penalizaciones daban scores sistematicamente negativos, lo cual hacia dificil comparar algoritmos.

---

## 3. Algoritmos comparados

### Random Search (baseline)

Genera K eventos al azar, evalua, y repite. Nunca converge.

Uso: baseline trivial para comparar.

### Hill Climbing

Busqueda local greedy: genera solucion inicial, en cada iteracion explora un vecino, si mejora se queda, si no lo descarta.

Problema: se atasca en optimos locales. No explora mas alla del primer pico.

### Simulated Annealing

Inspirado en el enfriamiento de metales (Kirkpatrick et al., 1983). El algoritmo:

1. Empieza con una solucion inicial y una temperatura alta.
2. En cada iteracion, genera un vecino y evalua si es mejor o peor.
3. Si es mejor, lo acepta. Si es peor, lo acepta con cierta probabilidad que depende de la temperatura.
4. La temperatura baja gradualmente.
5. Al final, la temperatura es tan baja que solo acepta mejoras (como Hill Climbing).

Ventaja: al principio explora mucho (escapa de optimos locales). Al final explota (refina).

Parametros: temperatura inicial 100, temperatura final 0.1, enfriamiento geometrico, 300 iteraciones.

---

## 4. Resultados experimentales

### Configuracion

- 300 eventos sinteticos.
- 10 escenarios de busqueda.
- 5 repeticiones por escenario (seeds distintas).
- Total: 150 ejecuciones por algoritmo.
- Seed base: 42.

### Resultados numericos

- Simulated Annealing: media -21.44, std 14.09, min -45.43, max +13.94.
- Hill Climbing: media -34.00, std 18.45, min -56.11, max +4.55.
- Random Search: media -91.86, std 18.86, min -123.57, max -58.60.

### Tests estadisticos

Se realizaron tests de Wilcoxon signed-rank (no parametrico) y se calculo el tamano del efecto (Cohen's d).

- SA vs HC: p = 0.0003, Cohen's d = 0.773. Efecto medio-grande. SA gana.
- SA vs Random: p = 0.0000, Cohen's d = 4.274. Efecto gigantesco. SA gana claramente.
- HC vs Random: p = 0.0000, Cohen's d = 3.132. Efecto grande. HC gana a Random.

### Interpretacion

1. SA gana a HC con significancia estadistica.
2. SA gana a Random por un margen enorme.
3. HC gana a Random pero pierde contra SA.
4. SA alcanza scores positivos (hasta +13.94), cosa que HC no logra.

### Trade-offs

- SA tiene mayor varianza (std 14.09): explora mas, alcanza picos mas altos.
- HC es mas estable pero no explora lo suficiente.
- Random es estable pero malo (siempre alrededor de -90).

Conclusion: SA ofrece el mejor equilibrio entre calidad y exploracion.

---

## 5. Justificacion de la eleccion

### Por que Simulated Annealing

1. Mejor score medio: -21.44 vs -34.00 (HC) vs -91.86 (Random).
2. Alcanza valores positivos, indicando que encuentra soluciones optimas reales.
3. Escapa de optimos locales mediante aceptacion probabilistica.
4. Ampliamente usado en problemas NP-hard similares (TSP, scheduling, VRP).

### Alternativas rechazadas

- Greedy puro: se atasca muy rapido.
- Algoritmos geneticos: requieren mas parametros, convergencia mas lenta en problemas pequenos.
- Busqueda tabu: mas compleja, no justificada para K=5.
- Programacion lineal entera: viable para K=5 pero no escala si K crece.

### Limitaciones

- Sensible a los parametros. Ajuste manual.
- No determinista: requiere semilla para reproducibilidad.
- Balance delicado entre exploracion y explotacion.

---

## 6. Simulacion de escenarios

### Generacion sintetica

Para reproducir experimentos sin depender de APIs externas, se generan eventos y escenarios de forma programatica con semilla fija.

Ventaja: 100 por ciento reproducible con seed fija.

### Monte Carlo

Para medir la robustez de un algoritmo, se ejecuta N veces con seeds distintas y se calculan estadisticas (media, desviacion estandar, percentiles).

Uso en Eventide: validar que SA supera a HC consistentemente, no por azar.

---

## 7. Referencias

- Kirkpatrick, Gelatt y Vecchi (1983). Optimization by Simulated Annealing. Science.
- Cerny (1985). Thermodynamical approach to the traveling salesman problem.
- Wilcoxon (1945). Individual Comparisons by Ranking Methods. Biometrics Bulletin.
- Cohen (1988). Statistical Power Analysis for the Behavioral Sciences.