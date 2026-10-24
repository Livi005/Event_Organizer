"""Compara Random vs Hill Climbing vs Simulated Annealing."""

import statistics

from eventide.core.optimizer import optimizar_agenda
from eventide.core.simulation import generar_escenarios, generar_eventos


def main():
    eventos = generar_eventos(n=200, seed=42)
    escenarios = generar_escenarios(n=20, seed=43)

    resultados = {"random": [], "hc": [], "sa": []}

    for algo in resultados:
        print(f"\nEjecutando {algo.upper()} sobre {len(escenarios)} escenarios...")
        for esc in escenarios:
            prefs = {
                "location": esc["location"],
                "categories": esc["categories"],
                "available_dates": esc["available_dates"],
                "duracion_maxima": esc["duracion_maxima"],
                "velocidad_kmh": esc["velocidad_kmh"],
            }
            _, score, _ = optimizar_agenda(
                eventos, prefs, cantidad=5, algoritmo=algo, seed=42
            )
            resultados[algo].append(score)

    print("\n" + "=" * 60)
    print("RESULTADOS")
    print("=" * 60)
    print(f"{'Algoritmo':<10} {'Media':>10} {'Std':>10} {'Min':>10} {'Max':>10}")
    print("-" * 60)

    for algo, scores in resultados.items():
        print(
            f"{algo:<10} "
            f"{statistics.mean(scores):>10.2f} "
            f"{statistics.stdev(scores):>10.2f} "
            f"{min(scores):>10.2f} "
            f"{max(scores):>10.2f}"
        )


if __name__ == "__main__":
    main()