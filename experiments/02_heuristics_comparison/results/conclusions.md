# Conclusiones - Experimento 2: Heuristicas

## Resultados

| Algoritmo | Score medio | Std | Min | Max |
|---|---|---|---|---|
| sa | -21.44 | 14.09 | -45.43 | 13.94 |
| hc | -34.00 | 18.45 | -56.11 | 4.55 |
| random | -91.86 | 18.86 | -123.57 | -58.60 |

## Tests estadisticos

| Comparacion | Wilcoxon p-value | Cohen's d |
|---|---|---|
| sa_vs_hc | 0.0003 | 0.773 |
| sa_vs_random | 0.0000 | 4.274 |
| hc_vs_random | 0.0000 | 3.132 |

## Conclusion

El mejor algoritmo es **sa** con score medio de **-21.44**.

**Justificacion:**

- Simulated Annealing explora mejor el espacio de soluciones.
- Escapa de optimos locales mediante aceptacion probabilistica.
- Mayor varianza a cambio de mejores picos de calidad.
