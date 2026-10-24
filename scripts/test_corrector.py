"""Test directo del corrector ortografico."""

from eventide.core.simulation import generar_eventos
from eventide.core.text_utils import CorrectorQuery, construir_vocabulario

# 1. Generar eventos y vocabulario
eventos = generar_eventos(n=200, seed=42)
vocab = construir_vocabulario(eventos)
print(f"Vocabulario: {len(vocab)} palabras")

# 2. Crear corrector
corrector = CorrectorQuery(vocab, idioma="es")

# 3. Probar correcciones
casos = [
    "balar",           # typo de bailar
    "conzierto",       # typo de concierto
    "muscia",          # typo de musica
    "exposicion",      # palabra correcta
    "bailar",          # palabra correcta (pero puede no estar en vocab)
    "fiesta",
]

for q in casos:
    corregida, sugerencias = corrector.corregir(q)
    estado = "SIN CAMBIO" if corregida == q else "CORREGIDA"
    print(f"\n  Original: {q!r}")
    print(f"  Corregida: {corregida!r}  [{estado}]")
    print(f"  Sugerencias: {sugerencias}")
