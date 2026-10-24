"""
Agente narrador: convierte una agenda optimizada en una explicacion
conversacional en lenguaje natural usando Gemini (o fallback local).

Decisiones de diseno:
- Analisis contextual, pero con UMBRALES para no mencionar datos absurdos.
- Fallback con bullets genericos razonables si no hay datos utiles.
- Nunca se mencionan distancias > 30 km ni huecos > 24 h.
- Se maneja el caso de location=None.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from geopy.distance import geodesic

from eventide.agents.base import AgenteBase, Mensaje
from eventide.config import settings
from eventide.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================
# UMBRALES (para no mencionar datos absurdos)
# =============================================================

MAX_DISTANCIA_MENCIONABLE_KM = 30.0
MAX_HUECO_MENCIONABLE_H = 24.0
MIN_EVENTOS_MISMA_CIUDAD = 3


# =============================================================
# PROMPT DEL SISTEMA
# =============================================================

SYSTEM_PROMPT = """Eres Evenity, el asistente personal de planes de Eventide.

Hablas como un amigo cercano que conoce bien la ciudad y quiere que la otra
persona la pase bien. Tono calido, cercano, natural. Tuteas siempre. Espanol
NEUTRO: nada de expresiones propias de un solo pais (evita "molar", "guay",
"tio", "rollo", "chevere", "bacano", "padre", "copado", "chido", etc.).

TU MISION
No se trata de listar eventos: se trata de contarle a la persona por que este
plan le va a funcionar, con detalles concretos pero sensatos.

ESTRUCTURA (respetala siempre)

1) SALUDO CORTO Y CALIDO
   Menciona la ciudad (si la hay) y, si sabes, el momento. Si el usuario
   hizo una busqueda concreta, reacciona a ella con naturalidad.
   Ejemplos validos (NO los copies, inspírate):
   - "Te prepare un plan en Madrid que creo que te va a gustar."
   - "Mira, estuve revisando opciones y encontre algo que encaja con lo que
     buscabas."
   - "Vi que querias algo de musica, asi que te arme un plan que combina
     concierto y algo de ambiente despues."
   NUNCA digas "en None" ni menciones valores vacios o sin sentido.

2) LISTA DE EVENTOS
   Cada evento en DOS lineas con este formato EXACTO:

       <emoji tematico> 1. DD MMM, HH:MM — Titulo real del evento
       📍 Lugar · Ciudad

   - Usa el TITULO REAL del evento. NUNCA la palabra "Evento".
   - SIEMPRE fecha (dia y mes) + hora. Ejemplo: "15 dic, 22:00".
   - Meses cortos: ene, feb, mar, abr, may, jun, jul, ago, sep, oct, nov, dic.
   - Emoji tematico segun categoria:
     concerts -> 🎸 | festivals -> 🎪 | theater -> 🎭 | arts -> 🎨
     sports -> ⚽ | food -> 🍽️ | technology -> 💻 | conferences -> 🎤
     literature -> 📚 | wellness -> 🧘

3) "POR QUE TE PROPONGO ESTO"
   Titulo de la seccion: "💡 Por que te lo propongo"
   3 o 4 bullets, cada uno empezando por "•".
   Reglas IMPORTANTES:
   - Solo menciona datos que sean SENSATOS y UTILES. No menciones distancias
     enormes, huecos gigantes, ni nada que suene mal.
   - Si los datos del analisis no son razonables, usa justificaciones mas
     generales pero honestas.
   - Suena como un amigo que recomienda, no como un log tecnico.
   - No repitas siempre las mismas frases; adaptalas al contexto.
   - NO uses palabras tecnicas: "categoria dominante", "optimizacion",
     "algoritmo", "huecos", "PageRank".

   Ejemplos de bullets validos:
   - "• Como pediste algo de musica, el primer evento es un concierto."
   - "• Son estilos distintos, para que pruebes cosas nuevas."
   - "• Los eventos no se solapan, asi puedes ir a todos sin elegir."
   - "• Estan ordenados por fecha y hora para que el plan fluya."

4) MENCION DE ALTERNATIVAS DESCARTADAS (opcional)
   Si te paso alternativas, menciona la mas relevante con honestidad.
   Ejemplo: "Tambien vi una opera esa noche, pero se solapaba con el festival.
   Si prefieres opera, dime y te la cambio."

5) CIERRE
   - "Si deseas cambiar algo, solo dime y lo ajusto."
   - "Si deseas cambiar algo o reservar alguna entrada, avisame."

REGLAS ESTRICTAS
- Emojis: maximo 6 en total.
- Longitud: entre 12 y 20 lineas.
- Espanol NEUTRO, sin regionalismos.
- NUNCA menciones: IDs, JSON, "None", scores crudos, "PageRank",
  "algoritmo", "SA", "optimizacion", "grafo".
- El score SOLO en el formato "✨ Score global: XX.X / 100".
- Si el score es negativo, se honesto.
- Si no tienes informacion suficiente, no inventes.
"""


# =============================================================
# AGENTE
# =============================================================

MESES_ABREV = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

EMOJI_CAT = {
    "concerts": "🎸", "festivals": "🎪", "theater": "🎭", "arts": "🎨",
    "sports": "⚽", "food": "🍽️", "technology": "💻", "conferences": "🎤",
    "literature": "📚", "wellness": "🧘",
}

NOMBRE_CAT = {
    "concerts": "musica en vivo",
    "festivals": "festivales",
    "theater": "teatro",
    "arts": "arte",
    "sports": "deporte",
    "food": "gastronomia",
    "technology": "tecnologia",
    "conferences": "conferencias",
    "literature": "literatura",
    "wellness": "bienestar",
}


class AgenteNarrador(AgenteBase):
    """Agente que narra agendas usando Gemini con fallback local."""

    def __init__(
        self,
        nombre: str = "narrador",
        usar_llm: bool = True,
        max_cache_size: int = 100,
        timeout_llm: float = 15.0,
    ) -> None:
        super().__init__(nombre)
        self.usar_llm = usar_llm
        self.max_cache_size = max_cache_size
        self.timeout_llm = timeout_llm
        self._cache: dict[str, str] = {}
        self._model = None
        self.narraciones_realizadas = 0
        self.narraciones_llm = 0
        self.narraciones_fallback = 0
        self.narraciones_cache_hit = 0

    # ---------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------

    def setup(self) -> None:
        if not self.usar_llm:
            self.logger.info("Narrador en modo fallback (LLM desactivado)")
            return

        if not settings.has_llm_key:
            self.logger.warning("Sin GEMINI_API_KEY: usando fallback local")
            self.usar_llm = False
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key.get_secret_value())
            self._model = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=SYSTEM_PROMPT,
            )

            ok = {"value": False}

            def _ping():
                try:
                    r = self._model.generate_content(
                        "Responde solo con: ok",
                        generation_config={"max_output_tokens": 5},
                    )
                    if r.text:
                        ok["value"] = True
                except Exception as e:
                    self.logger.warning(f"Health check Gemini fallo: {e}")

            hilo = threading.Thread(target=_ping, daemon=True)
            hilo.start()
            hilo.join(timeout=8.0)

            if not ok["value"]:
                self.logger.warning(
                    "Gemini no responde en 8s. Activando modo fallback."
                )
                self.usar_llm = False
                return

            self.logger.info(f"Gemini OK: modelo={settings.gemini_model}")

        except Exception as e:
            self.logger.error(f"Error inicializando Gemini: {e}")
            self.usar_llm = False

    # ---------------------------------------------------------
    # MANEJO DE MENSAJES
    # ---------------------------------------------------------

    def manejar_mensaje(self, msg: Mensaje) -> None:
        if msg.tipo == "narrar":
            self._handle_narrar(msg)
        elif msg.tipo == "stats":
            self._handle_stats(msg)
        elif msg.tipo == "limpiar_cache":
            self._cache.clear()
            self._responder(msg, "cache_limpiada", {"ok": True})
        else:
            self.logger.debug(f"Tipo no soportado: {msg.tipo}")

    # ---------------------------------------------------------
    # HANDLERS
    # ---------------------------------------------------------

    def _handle_narrar(self, msg: Mensaje) -> None:
        payload = msg.payload

        agenda = payload.get("agenda") or []
        preferencias = payload.get("preferencias") or {}
        scores_grafo = payload.get("scores_grafo")
        query_original = payload.get("query_original")
        alternativas = payload.get("alternativas_descartadas") or []

        if not agenda:
            self._responder(msg, "narracion_lista", {
                "texto": "Vaya, no encontre nada que encaje con lo que "
                         "buscabas. Deseas que amplie la busqueda o que "
                         "ajuste las preferencias?",
                "fuente": "fallback",
                "tiempo_ms": 0,
                "cache_hit": False,
                "analisis": {},
            })
            return

        # Analisis contextual con UMBRALES aplicados
        analisis = self._analizar_contexto(agenda, preferencias, query_original)

        cache_key = self._hash_agenda(agenda, preferencias)
        if cache_key in self._cache:
            self.narraciones_cache_hit += 1
            self._responder(msg, "narracion_lista", {
                "texto": self._cache[cache_key],
                "fuente": "cache",
                "tiempo_ms": 0,
                "cache_hit": True,
                "analisis": analisis,
            })
            return

        t0 = time.perf_counter()

        if self.usar_llm and self._model is not None:
            try:
                texto = self._narrar_con_llm(
                    agenda, preferencias, scores_grafo, query_original,
                    alternativas, analisis,
                )
                fuente = "llm"
                self.narraciones_llm += 1
            except Exception as e:
                self.logger.error(f"Error en LLM, usando fallback: {e}")
                texto = self._narrar_fallback(
                    agenda, preferencias, alternativas, analisis
                )
                fuente = "fallback"
                self.narraciones_fallback += 1
        else:
            texto = self._narrar_fallback(
                agenda, preferencias, alternativas, analisis
            )
            fuente = "fallback"
            self.narraciones_fallback += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.narraciones_realizadas += 1

        self._guardar_cache(cache_key, texto)

        self.logger.info(
            f"Narracion generada: fuente={fuente}, "
            f"tiempo={elapsed_ms:.1f}ms, chars={len(texto)}"
        )

        self._responder(msg, "narracion_lista", {
            "texto": texto,
            "fuente": fuente,
            "tiempo_ms": round(elapsed_ms, 2),
            "cache_hit": False,
            "analisis": analisis,
        })

    def _handle_stats(self, msg: Mensaje) -> None:
        self._responder(msg, "stats_narrador", {
            "narraciones_realizadas": self.narraciones_realizadas,
            "narraciones_llm": self.narraciones_llm,
            "narraciones_fallback": self.narraciones_fallback,
            "narraciones_cache_hit": self.narraciones_cache_hit,
            "usar_llm": self.usar_llm,
            "cache_size": len(self._cache),
        })

    # ---------------------------------------------------------
    # ANALISIS CONTEXTUAL (con filtros de sensatez)
    # ---------------------------------------------------------

    @staticmethod
    def _analizar_contexto(
        agenda: list[dict[str, Any]],
        preferencias: dict[str, Any],
        query_original: str | None,
    ) -> dict[str, Any]:
        """
        Extrae info concreta sobre la agenda, aplicando filtros de sensatez:
        - Solo marca 'todos_cerca' si la distancia maxima es < 30 km.
        - Solo marca 'huecos_pequenos' si el hueco promedio es < 24 h.
        - Nunca expone valores absurdos como datos utiles.
        """
        analisis: dict[str, Any] = {}

        # --- Ciudades ---
        ciudades = [
            ev.get("spatial_info", {}).get("area", {}).get("city")
            for ev in agenda
        ]
        ciudades = [c for c in ciudades if c]
        analisis["ciudades_unicas"] = sorted(set(ciudades))
        analisis["misma_ciudad"] = (
            len(set(ciudades)) == 1 and len(ciudades) >= MIN_EVENTOS_MISMA_CIUDAD
        )

        # --- Categorias ---
        cats = [
            ev.get("classification", {}).get("primary_category")
            for ev in agenda
        ]
        cats = [c for c in cats if c]
        analisis["categorias_unicas"] = sorted(set(cats))
        analisis["diversidad_categorias"] = len(set(cats))

        if cats:
            from collections import Counter
            contador = Counter(cats)
            cat_dom, count_dom = contador.most_common(1)[0]
            analisis["categoria_dominante"] = cat_dom
            analisis["categoria_dominante_count"] = count_dom
            analisis["nombre_categoria_dominante"] = NOMBRE_CAT.get(
                cat_dom, cat_dom
            )
        else:
            analisis["categoria_dominante"] = None
            analisis["categoria_dominante_count"] = 0
            analisis["nombre_categoria_dominante"] = None

        # --- Coordenadas y distancias (solo si son sensatas) ---
        coords = []
        for ev in agenda:
            loc = ev.get("spatial_info", {}).get("venue", {}).get("location", {})
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat is not None and lon is not None:
                coords.append((lat, lon))

        if len(coords) >= 2:
            distancias = []
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    try:
                        d = geodesic(coords[i], coords[j]).km
                        distancias.append(d)
                    except Exception:
                        pass

            if distancias:
                dist_max = max(distancias)
                dist_prom = sum(distancias) / len(distancias)
                analisis["distancia_maxima_km"] = round(dist_max, 1)
                analisis["distancia_promedio_km"] = round(dist_prom, 1)

                # Solo marcamos "cerca" si es razonable
                if dist_max < MAX_DISTANCIA_MENCIONABLE_KM:
                    analisis["todos_cerca"] = True
                    analisis["distancia_mencionable"] = True
                else:
                    analisis["todos_cerca"] = False
                    analisis["distancia_mencionable"] = False

        # --- Fechas y huecos (solo si son sensatos) ---
        eventos_con_fecha = []
        for ev in agenda:
            start_raw = ev.get("temporal_info", {}).get("start")
            if start_raw:
                try:
                    dt = datetime.fromisoformat(
                        str(start_raw).replace("Z", "+00:00")
                    )
                    dur = ev.get("temporal_info", {}).get(
                        "duration_minutes", 120
                    ) or 120
                    eventos_con_fecha.append((dt, dur))
                except (ValueError, AttributeError):
                    pass

        if len(eventos_con_fecha) >= 2:
            eventos_con_fecha.sort(key=lambda x: x[0])
            huecos = []
            for i in range(len(eventos_con_fecha) - 1):
                fin_actual = eventos_con_fecha[i][0] + timedelta(
                    minutes=eventos_con_fecha[i][1]
                )
                siguiente = eventos_con_fecha[i + 1][0]
                gap_h = (siguiente - fin_actual).total_seconds() / 3600
                if gap_h > 0:
                    huecos.append(gap_h)

            if huecos:
                hueco_prom = sum(huecos) / len(huecos)
                analisis["huecos_promedio_horas"] = round(hueco_prom, 1)

                # Solo marcamos "pequenos" si es razonable
                if hueco_prom < MAX_HUECO_MENCIONABLE_H:
                    analisis["huecos_pequenos"] = True
                    analisis["huecos_mencionable"] = True
                else:
                    analisis["huecos_pequenos"] = False
                    analisis["huecos_mencionable"] = False

        # --- Coincidencia con la query ---
        if query_original:
            analisis["query_original"] = query_original
            keywords = [
                w.lower() for w in query_original.split()
                if len(w) > 3
            ]
            analisis["query_keywords"] = keywords[:3]

            texto_agenda = " ".join(
                (
                    ev.get("basic_info", {}).get("title", "") + " " +
                    ev.get("classification", {}).get("primary_category", "")
                ).lower()
                for ev in agenda
            )
            coincidencias = sum(1 for kw in keywords if kw in texto_agenda)
            analisis["coincide_con_query"] = coincidencias > 0

        # --- Preferencias (manejar None) ---
        loc_pref = preferencias.get("location")
        if loc_pref:
            analisis["preferencia_ciudad"] = loc_pref

        return analisis

    # ---------------------------------------------------------
    # LLM
    # ---------------------------------------------------------

    def _narrar_con_llm(
        self,
        agenda: list[dict[str, Any]],
        preferencias: dict[str, Any],
        scores_grafo: dict[str, float] | None,
        query_original: str | None,
        alternativas: list[dict[str, Any]],
        analisis: dict[str, Any],
    ) -> str:
        prompt_usuario = self._construir_prompt_usuario(
            agenda, preferencias, scores_grafo, query_original,
            alternativas, analisis,
        )

        resultado: dict[str, Any] = {"texto": None, "error": None}

        def _llamar():
            try:
                response = self._model.generate_content(
                    prompt_usuario,
                    generation_config={
                        "temperature": 0.85,
                        "max_output_tokens": 900,
                        "top_p": 0.95,
                    },
                    safety_settings={
                        "HARASSMENT": "BLOCK_NONE",
                        "HATE": "BLOCK_NONE",
                        "SEXUAL": "BLOCK_NONE",
                        "DANGEROUS": "BLOCK_NONE",
                    },
                )
                texto = response.text.strip()
                if not texto:
                    raise RuntimeError("Respuesta vacia de Gemini")
                resultado["texto"] = texto
            except Exception as e:
                resultado["error"] = str(e)

        hilo = threading.Thread(target=_llamar, daemon=True)
        hilo.start()
        hilo.join(timeout=self.timeout_llm)

        if hilo.is_alive():
            raise TimeoutError(f"Gemini tardo mas de {self.timeout_llm}s")

        if resultado["error"]:
            raise RuntimeError(resultado["error"])

        if not resultado["texto"]:
            raise RuntimeError("Gemini devolvio respuesta vacia")

        return resultado["texto"]

    @staticmethod
    def _construir_prompt_usuario(
        agenda: list[dict[str, Any]],
        preferencias: dict[str, Any],
        scores_grafo: dict[str, float] | None,
        query_original: str | None,
        alternativas: list[dict[str, Any]],
        analisis: dict[str, Any],
    ) -> str:
        lineas = []

        lineas.append("=== CONTEXTO DEL USUARIO ===")
        if query_original:
            lineas.append(f'El usuario busco: "{query_original}"')
        loc = preferencias.get("location")
        if loc:
            lineas.append(f"Ciudad preferida: {loc}")
        cats = preferencias.get("categories") or []
        if cats:
            lineas.append(f"Le interesan cosas tipo: {', '.join(cats)}")

        lineas.append("\n=== AGENDA PROPUESTA ===")
        agenda_ordenada = sorted(
            agenda,
            key=lambda e: str(e.get("temporal_info", {}).get("start") or ""),
        )
        for i, ev in enumerate(agenda_ordenada, 1):
            basic = ev.get("basic_info", {})
            temporal = ev.get("temporal_info", {})
            spatial = ev.get("spatial_info", {})
            cat = ev.get("classification", {}).get("primary_category", "")
            venue = spatial.get("venue", {}).get("name", "lugar")
            city = spatial.get("area", {}).get("city", "")
            start = temporal.get("start", "")
            dur = temporal.get("duration_minutes", "?")
            fecha_fmt = AgenteNarrador._formatear_fecha(start)

            lineas.append(
                f"\n#{i}"
                f"\n  Titulo: {basic.get('title', 'sin titulo')}"
                f"\n  Fecha: {fecha_fmt}"
                f"\n  Duracion: {dur} min"
                f"\n  Lugar: {venue}"
                f"\n  Ciudad: {city}"
                f"\n  Tipo: {cat}"
            )

        # Analisis contextual, pero SOLO los campos utiles
        datos_utiles = {}
        if analisis.get("coincide_con_query"):
            datos_utiles["coincide_con_query"] = True
            datos_utiles["query_keywords"] = analisis.get("query_keywords", [])
        if analisis.get("todos_cerca") and analisis.get("distancia_mencionable"):
            datos_utiles["todos_cerca"] = True
            datos_utiles["distancia_maxima_km"] = analisis.get("distancia_maxima_km")
        if analisis.get("huecos_pequenos") and analisis.get("huecos_mencionable"):
            datos_utiles["huecos_pequenos"] = True
            datos_utiles["huecos_promedio_horas"] = analisis.get("huecos_promedio_horas")
        if analisis.get("misma_ciudad"):
            datos_utiles["misma_ciudad"] = True
            datos_utiles["ciudades_unicas"] = analisis.get("ciudades_unicas")
        if analisis.get("diversidad_categorias", 0) >= 2:
            datos_utiles["diversidad_categorias"] = analisis["diversidad_categorias"]
            datos_utiles["categorias_unicas"] = analisis.get("categorias_unicas")
        if analisis.get("nombre_categoria_dominante"):
            datos_utiles["nombre_categoria_dominante"] = analisis["nombre_categoria_dominante"]

        if datos_utiles:
            lineas.append("\n=== DATOS REALES QUE PUEDES USAR ===")
            lineas.append(
                "Estos datos son SENSATOS y verificados. Puedes mencionarlos "
                "con naturalidad para justificar la agenda:"
            )
            for k, v in datos_utiles.items():
                lineas.append(f"  - {k}: {v}")
        else:
            lineas.append(
                "\n=== DATOS REALES ===\n"
                "No hay datos contextuales utiles para mencionar. Usa "
                "justificaciones generales pero honestas."
            )

        if alternativas:
            lineas.append("\n=== ALTERNATIVAS DESCARTADAS ===")
            for alt in alternativas[:2]:
                basic = alt.get("basic_info", {})
                razon = alt.get("_razon_descarte", "no encajaba del todo")
                lineas.append(
                    f"\n- {basic.get('title', 'sin titulo')}"
                    f"\n  Razon: {razon}"
                )

        lineas.append(
            "\n=== TU TAREA ===\n"
            "Cuentale a la persona su plan siguiendo ESTRICTAMENTE el ESTILO "
            "y la ESTRUCTURA de tu system prompt. En el bloque "
            "'💡 Por que te lo propongo' usa los datos reales disponibles "
            "para justificar, con lenguaje natural. No menciones jamas: "
            "None, distancias enormes, huecos de cientos de horas ni nada "
            "que suene a log tecnico."
        )

        return "\n".join(lineas)

    # ---------------------------------------------------------
    # FALLBACK LOCAL
    # ---------------------------------------------------------

    @staticmethod
    def _narrar_fallback(
        agenda: list[dict[str, Any]],
        preferencias: dict[str, Any],
        alternativas: list[dict[str, Any]] | None,
        analisis: dict[str, Any],
    ) -> str:
        alternativas = alternativas or []
        ciudad = preferencias.get("location") or "tu zona"
        query = analisis.get("query_original", "")
        coincide = analisis.get("coincide_con_query", False)

        # ---- Saludo ----
        if query and coincide:
            saludo = (
                f"Mira, te prepare un plan relacionado con lo que buscabas. "
                f"Creo que te va a gustar."
            )
        elif query:
            saludo = (
                f"Te cuento: busque algo de lo que pediste y te arme este "
                f"plan. Ojala encaje con lo que tenias en mente."
            )
        else:
            saludo = (
                f"Te prepare un plan que creo que te va a gustar. Sin "
                f"complicaciones: unas cuantas paradas y a disfrutar."
            )

        lineas = [saludo, ""]

        # ---- Eventos ----
        agenda_ordenada = sorted(
            agenda,
            key=lambda e: str(e.get("temporal_info", {}).get("start") or ""),
        )
        for i, ev in enumerate(agenda_ordenada, 1):
            basic = ev.get("basic_info", {})
            temporal = ev.get("temporal_info", {})
            spatial = ev.get("spatial_info", {})
            cat = ev.get("classification", {}).get("primary_category", "")

            titulo = basic.get("title", "Evento")
            venue = spatial.get("venue", {}).get("name", "lugar por confirmar")
            city = spatial.get("area", {}).get("city", "")
            start = str(temporal.get("start") or "")
            emoji = EMOJI_CAT.get(cat, "📌")
            fecha_hora = AgenteNarrador._formatear_fecha(start)

            lugar_txt = venue
            if city:
                lugar_txt += f" · {city}"

            lineas.append(f"{emoji} {i}. {fecha_hora} — {titulo}")
            lineas.append(f"📍 {lugar_txt}")
            lineas.append("")

        # ---- Bullets ----
        lineas.append("💡 Por que te lo propongo")
        bullets = AgenteNarrador._generar_bullets(analisis)
        for b in bullets:
            lineas.append(b)

        if alternativas:
            alt = alternativas[0]
            basic = alt.get("basic_info", {})
            razon = alt.get("_razon_descarte", "no encajaba del todo")
            lineas.append(
                f"• Tambien vi \"{basic.get('title', 'otro evento')}\", pero "
                f"lo deje fuera: {razon}."
            )

        lineas.append("")
        lineas.append("✨ Score global: calculado por el optimizador")
        lineas.append("")
        lineas.append("Si deseas cambiar algo, solo dime y lo ajusto.")

        return "\n".join(lineas)

    @staticmethod
    def _generar_bullets(analisis: dict[str, Any]) -> list[str]:
        """
        Genera 3-4 bullets SENSATOS. Solo usa datos que pasen los umbrales.
        """
        bullets: list[str] = []

        # Bullet 1: coincidencia con la query
        if analisis.get("coincide_con_query"):
            kw = analisis.get("query_keywords", [])
            if kw:
                kw_str = ", ".join(kw[:2])
                bullets.append(
                    f"• Como pediste algo de {kw_str}, ordene los eventos "
                    f"para que la experiencia sea coherente con esa busqueda."
                )

        # Bullet 2: diversidad o concentracion (nunca tecnicismos)
        diversidad = analisis.get("diversidad_categorias", 0)
        nombre_cat_dom = analisis.get("nombre_categoria_dominante")

        if diversidad >= 3:
            bullets.append(
                "• Hay estilos distintos en el plan, para que puedas probar "
                "cosas nuevas sin quedarte en lo de siempre."
            )
        elif nombre_cat_dom:
            bullets.append(
                f"• La mayoria son eventos de {nombre_cat_dom}, para "
                f"mantener la misma onda durante todo el plan."
            )

        # Bullet 3: distancia (SOLO si es sensata)
        if analisis.get("todos_cerca") and analisis.get("distancia_mencionable"):
            dist = analisis.get("distancia_maxima_km", 0)
            bullets.append(
                f"• Los lugares estan a menos de {dist} km entre si, asi "
                f"no pierdes tiempo en traslados."
            )

        # Bullet 4: huecos (SOLO si son sensatos)
        if analisis.get("huecos_pequenos") and analisis.get("huecos_mencionable"):
            huecos = analisis.get("huecos_promedio_horas", 0)
            bullets.append(
                f"• Los espacios entre eventos son de unas {huecos} h, para "
                f"que puedas ir con calma."
            )

        # Bullet 5: misma ciudad
        if analisis.get("misma_ciudad"):
            ciudades = analisis.get("ciudades_unicas", [])
            if ciudades:
                bullets.append(
                    f"• Todos los eventos son en {ciudades[0]}, asi no "
                    f"tienes que desplazarte entre ciudades."
                )

        # Rellenar con genericos sensatos si faltan
        genericos = [
            "• Me asegure de que no se solapen, para que puedas ir a todos "
            "sin tener que elegir.",
            "• Los eventos estan ordenados por fecha y hora para que el "
            "plan fluya.",
            "• Eleji eventos que encajan con lo que sueles disfrutar.",
        ]
        for g in genericos:
            if len(bullets) >= 3:
                break
            bullets.append(g)

        return bullets[:4]

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _formatear_fecha(iso_str: str) -> str:
        if not iso_str:
            return "fecha por confirmar"
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            mes = MESES_ABREV.get(dt.month, f"{dt.month:02d}")
            return f"{dt.day:02d} {mes}, {dt.hour:02d}:{dt.minute:02d}"
        except (ValueError, AttributeError, TypeError):
            return str(iso_str)

    @staticmethod
    def _hash_agenda(
        agenda: list[dict[str, Any]],
        preferencias: dict[str, Any],
    ) -> str:
        ids = sorted(
            str(ev.get("id") or ev.get("basic_info", {}).get("title", ""))
            for ev in agenda
        )
        clave = {
            "ids": ids,
            "location": preferencias.get("location"),
            "categories": sorted(preferencias.get("categories") or []),
        }
        raw = json.dumps(clave, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def _guardar_cache(self, key: str, texto: str) -> None:
        if len(self._cache) >= self.max_cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = texto

    def _responder(self, msg: Mensaje, tipo: str, payload: dict[str, Any]) -> None:
        destino = msg.payload.get("respuesta_a")
        if destino:
            self.enviar(destino, tipo, payload)
        else:
            self.logger.warning(f"Sin respuesta_a, no puedo responder {tipo}")