"""
Utilidades de texto: correccion ortografica y sugerencias.

Usa pyspellchecker sobre un vocabulario construido a partir de los eventos
(titulos + categorias + ciudades + artistas).
"""

from __future__ import annotations

import re
from typing import Iterable

from spellchecker import SpellChecker

from eventide.logging_config import get_logger

logger = get_logger(__name__)


_STOPWORDS = {
    "de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "que",
    "con", "por", "para", "del", "al", "es", "son", "mi", "tu", "su",
    "lo", "se", "si", "no", "me", "te", "le", "nos", "os", "les",
    "muy", "mas", "menos", "o", "u", "pero", "ya", "the", "of",
    "and", "to", "in", "on", "at", "for", "with",
}

MIN_LEN = 4

# =============================================================
# CONFUSIONES COMUNES
# =============================================================
# Palabras que son validas en el diccionario espanol pero que
# en el contexto de eventos suelen ser un typo de otra palabra
# mas frecuente.

CONFUSIONES_COMUNES: dict[str, str] = {
    # bailar / balar
    "balar": "bailar",
    "vailar": "bailar",
    "baylar": "bailar",
    "baliar": "bailar",
    # comer / beber
    "commer": "comer",
    "bever": "beber",
    # musica / concierto
    "muscia": "musica",
    "conzierto": "concierto",
    "concierto": "concierto",
    # fiesta / festival
    "festa": "fiesta",
    "festial": "festival",
    # teatro
    "teatro": "teatro",
    "theatro": "teatro",
    # arte
    "arto": "arte",
    # deporte
    "deporto": "deporte",
    # tecnologia
    "tecnolgia": "tecnologia",
    "tecnologia": "tecnologia",
}

SINONIMOS_TEMATICOS = {
    "bailar": ["concierto", "festival", "baile", "fiesta", "musica en vivo"],
    "balar": ["concierto", "festival", "baile", "fiesta", "musica en vivo"],
    "comer": ["gastronomia", "restaurante", "food"],
    "beber": ["bar", "cerveza", "coctel"],
    "arte": ["exposicion", "museo", "galeria"],
}

def _tokenize(texto: str) -> list[str]:
    """Tokeniza, minusculas, sin acentos ni puntuacion."""
    texto = texto.lower()
    acentos = str.maketrans(
        "����������������������",
        "aeiouaeiouaeiouaeiounc",
    )
    texto = texto.translate(acentos)
    return re.findall(r"\b[a-z]+\b", texto)


def construir_vocabulario(eventos: Iterable[dict]) -> set[str]:
    """Vocabulario a partir de titulos, categorias, ciudades y artistas."""
    vocab: set[str] = set()

    for ev in eventos:
        basic = ev.get("basic_info", {})
        for key in ("title", "description"):
            texto = basic.get(key, "")
            if texto:
                for w in _tokenize(texto):
                    if w not in _STOPWORDS and len(w) >= MIN_LEN:
                        vocab.add(w)

        cat = ev.get("classification", {}).get("primary_category", "")
        if cat:
            for w in _tokenize(cat):
                vocab.add(w)

        city = ev.get("spatial_info", {}).get("area", {}).get("city", "")
        if city:
            for w in _tokenize(city):
                vocab.add(w)

        for p in ev.get("participants", {}).get("performers", []):
            name = p.get("name", "")
            if name:
                for w in _tokenize(name):
                    if len(w) >= MIN_LEN:
                        vocab.add(w)

    return vocab


class CorrectorQuery:
    """
    Corrector de queries con vocabulario de eventos.

    Corrige solo si:
    - La palabra no esta en el vocabulario.
    - Existe una correccion con distancia <= 2.
    - La correccion esta en el vocabulario.
    """

    def __init__(
        self,
        vocabulario: set[str],
        idioma: str = "es",
        distancia_max: int = 2,
    ) -> None:
        self.vocabulario = vocabulario
        self.spell = SpellChecker(language=idioma, distance=distancia_max)
        self.spell.word_frequency.load_words(vocabulario)
        self.idioma = idioma

    def corregir(self, query: str) -> tuple[str, list[dict]]:
        """
        Corrige la query.

        Returns:
            (query_corregida, sugerencias)
            donde cada sugerencia es {"palabra_original", "sugerencia", "alternativas"}
        """
        if not query.strip():
            return query, []

        tokens = re.findall(r"[\wáéíóúñÁÉÍÓÚÑ]+|[^\w\s]+|\s+", query)

        sugerencias: list[dict] = []
        resultado_tokens: list[str] = []

        for token in tokens:
            if not re.match(r"[\wáéíóúñÁÉÍÓÚÑ]+", token):
                resultado_tokens.append(token)
                continue

            token_norm = _tokenize(token)
            if not token_norm:
                resultado_tokens.append(token)
                continue

            palabra = token_norm[0]

            if len(palabra) < MIN_LEN or palabra in _STOPWORDS:
                resultado_tokens.append(token)
                continue
            
            if palabra in CONFUSIONES_COMUNES:
                mejor = CONFUSIONES_COMUNES[palabra]
                if mejor != palabra:
                    resultado_tokens.append(mejor)
                    sugerencias.append({
                        "palabra_original": token,
                        "sugerencia": mejor,
                        "alternativas": [mejor],
                        "motivo": "confusion_comun",
                    })
                    continue
                else:
                    resultado_tokens.append(token)
                    continue

            if palabra in self.vocabulario:
                resultado_tokens.append(token)
                continue

            # Buscar candidatos (del diccionario del idioma)
            candidatos = self.spell.candidates(palabra)
            if not candidatos:
                resultado_tokens.append(token)
                continue

            # Filtrar candidatos:
            # 1. Priorizar los que están en el vocabulario de eventos.
            # 2. Si no hay, aceptar candidatos del diccionario general
            #    que tengan frecuencia alta (palabras comunes).
            del_vocab = [
                c for c in candidatos
                if c in self.vocabulario and c != palabra
            ]

            if del_vocab:
                candidatos_validos = del_vocab
            else:
                candidatos_validos = [
                    c for c in candidatos
                    if c != palabra and self.spell.word_frequency[c] >= 10
                ]

            if not candidatos_validos:
                resultado_tokens.append(token)
                continue

            mejor = max(
                candidatos_validos,
                key=lambda c: self.spell.word_frequency[c],
            )

            resultado_tokens.append(mejor)
            sugerencias.append({
                "palabra_original": token,
                "sugerencia": mejor,
                "alternativas": sorted(candidatos_validos)[:3],
            })

        query_corregida = "".join(resultado_tokens)
        return query_corregida, sugerencias