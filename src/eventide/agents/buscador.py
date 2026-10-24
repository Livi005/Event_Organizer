"""
Agente de busqueda semantica.

Envuelve EventEmbedder y expone busqueda + filtros por mensajes.
Incluye:
- Correccion ortografica basica (con vocabulario de eventos).
- "Did you mean" a nivel de busqueda: si hay pocos resultados, prueba
  variantes de la query y elige la que devuelve mas.
"""

from __future__ import annotations

from typing import Any

from eventide.agents.base import AgenteBase, Mensaje
from eventide.core.embedding import EventEmbedder
from eventide.core.simulation import generar_eventos


class AgenteBuscador(AgenteBase):
    """Agente que realiza busquedas semanticas con correccion ortografica."""

    def __init__(
        self,
        nombre: str = "buscador",
        usar_datos_sinteticos: bool = True,
        n_eventos_sinteticos: int = 200,
    ) -> None:
        super().__init__(nombre)
        self.usar_datos_sinteticos = usar_datos_sinteticos
        self.n_eventos_sinteticos = n_eventos_sinteticos
        self.embedder: EventEmbedder | None = None
        self.corrector = None
        self._ready = False

    # ---------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------

    def setup(self) -> None:
        try:
            self._setup_impl()
        finally:
            self._ready = True

    def _setup_impl(self) -> None:
        self.logger.info("Inicializando motor de busqueda...")

        # Intento 1: cargar desde disco
        try:
            self.embedder = EventEmbedder.load()
            self.logger.info(
                f"Embedder cargado desde disco: {self.embedder.num_events} eventos"
            )
            self._construir_corrector()
            return
        except FileNotFoundError:
            self.logger.warning("No hay embeddings en disco. Buscando alternativa...")

        # Intento 2: reutilizar singleton existente
        try:
            self.embedder = EventEmbedder.get_instance()
            if self.embedder.num_events > 0:
                self.logger.info(
                    f"Reutilizando embedder: {self.embedder.num_events} eventos"
                )
                self._construir_corrector()
                return
        except RuntimeError:
            pass

        # Intento 3: sinteticos
        if not self.usar_datos_sinteticos:
            raise RuntimeError(
                "No hay embeddings disponibles y no se permiten sinteticos"
            )

        self.logger.warning("Generando datos sinteticos de arranque...")
        eventos = generar_eventos(n=self.n_eventos_sinteticos, seed=42)

        EventEmbedder.reset()
        self.embedder = EventEmbedder()
        self.embedder.generate_embeddings(eventos)
        self.embedder.build_index(index_type="flat")
        self.embedder.build_shards()

        self.logger.info(
            f"Embedder listo con {self.embedder.num_events} eventos sinteticos"
        )
        self._construir_corrector()

    def _construir_corrector(self) -> None:
        """Construye el corrector ortografico con el vocabulario de eventos."""
        try:
            from eventide.core.text_utils import (
                CorrectorQuery,
                construir_vocabulario,
            )

            if self.embedder is None:
                self.corrector = None
                return

            vocabulario = construir_vocabulario(self.embedder.events)
            self.corrector = CorrectorQuery(vocabulario, idioma="es")
            self.logger.info(
                f"Corrector ortografico listo. Vocabulario: "
                f"{len(vocabulario)} palabras"
            )
        except Exception as e:
            self.logger.warning(f"Corrector no disponible: {e}")
            self.corrector = None

    @property
    def ready(self) -> bool:
        return self._ready and self.embedder is not None

    # ---------------------------------------------------------
    # MANEJO DE MENSAJES
    # ---------------------------------------------------------

    def manejar_mensaje(self, msg: Mensaje) -> None:
        if msg.tipo == "buscar":
            self._handle_buscar(msg)
        elif msg.tipo == "recargar":
            self._handle_recargar(msg)
        elif msg.tipo == "stats":
            self._handle_stats(msg)
        else:
            self.logger.debug(f"Tipo no soportado: {msg.tipo}")

    # ---------------------------------------------------------
    # HANDLERS
    # ---------------------------------------------------------

    def _handle_buscar(self, msg: Mensaje) -> None:
        payload = msg.payload

        query = (payload.get("query") or "").strip()
        if not query:
            self._responder(
                msg, "resultados_busqueda",
                {"query": "", "resultados": [], "total": 0, "error": "query vacia"},
            )
            return

        ciudad = payload.get("ciudad")
        categoria = payload.get("categoria")
        fecha_inicio = payload.get("fecha_inicio")
        fecha_fin = payload.get("fecha_fin")
        k = int(payload.get("k", 60))

        # --- Correccion ortografica basica ---
        sugerencias: list[dict] = []
        query_corregida = query
        if self.corrector is not None:
            try:
                query_corregida, sugerencias = self.corrector.corregir(query)
                if query_corregida != query:
                    self.logger.info(
                        f"Query corregida: {query!r} -> {query_corregida!r}"
                    )
            except Exception as e:
                self.logger.warning(f"Error en corrector: {e}")

        try:
            self.logger.info(
                f"Buscando: query={query_corregida!r} ciudad={ciudad} "
                f"categoria={categoria} k={k}"
            )

            if self.embedder is None:
                raise RuntimeError("Embedder no inicializado")

            usar_filtros = any([ciudad, categoria, fecha_inicio, fecha_fin])

            # Busqueda principal
            resultados = self._ejecutar_busqueda(
                query_corregida, ciudad, categoria,
                fecha_inicio, fecha_fin, k, usar_filtros,
            )

            # --- "Did you mean" a nivel de busqueda ---
            # Si hay pocos resultados, probar variantes
            variantes_probadas: list[dict] = []
            if len(resultados) < 3:
                self.logger.info(
                    f"Pocos resultados ({len(resultados)}), probando variantes..."
                )
                variantes = self._generar_variantes(query_corregida)
                for variante in variantes:
                    if variante == query_corregida:
                        continue
                    resultados_variante = self._ejecutar_busqueda(
                        variante, ciudad, categoria,
                        fecha_inicio, fecha_fin, k, usar_filtros,
                    )
                    if len(resultados_variante) > len(resultados):
                        variantes_probadas.append({
                            "variante": variante,
                            "total": len(resultados_variante),
                        })
                        # Si mejora mucho, usar esa busqueda
                        if len(resultados_variante) >= 3:
                            self.logger.info(
                                f"Variante '{variante}' da "
                                f"{len(resultados_variante)} resultados. "
                                f"Usandola."
                            )
                            resultados = resultados_variante
                            # Marcar la sugerencia
                            sugerencias.append({
                                "palabra_original": query,
                                "sugerencia": variante,
                                "alternativas": [
                                    v["variante"] for v in variantes_probadas
                                ],
                                "motivo": "no_results",
                            })
                            break

            limpios = [self._limpiar_evento(r) for r in resultados]

            self.logger.info(f"Encontrados {len(limpios)} resultados")

            self._responder(
                msg, "resultados_busqueda",
                {
                    "query": query,
                    "query_corregida": (
                        query_corregida if query_corregida != query else None
                    ),
                    "variantes_probadas": variantes_probadas,
                    "sugerencias": sugerencias,
                    "resultados": limpios,
                    "total": len(limpios),
                    "filtros": {
                        "ciudad": ciudad,
                        "categoria": categoria,
                        "fecha_inicio": fecha_inicio,
                        "fecha_fin": fecha_fin,
                    },
                },
            )

        except Exception as e:
            self.logger.error(f"Error en busqueda: {e}", exc_info=True)
            self._responder(
                msg, "resultados_busqueda",
                {
                    "query": query,
                    "query_corregida": None,
                    "sugerencias": sugerencias,
                    "resultados": [],
                    "total": 0,
                    "error": str(e),
                },
            )

    def _ejecutar_busqueda(
        self,
        query: str,
        ciudad: str | None,
        categoria: str | None,
        fecha_inicio: str | None,
        fecha_fin: str | None,
        k: int,
        usar_filtros: bool,
    ) -> list[dict]:
        """Ejecuta la busqueda con o sin filtros."""
        if self.embedder is None:
            return []

        if usar_filtros:
            resultados, _ = self.embedder.filtered_search(
                query=query,
                city=ciudad,
                category=categoria,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                k=k,
            )
        else:
            resultados, _ = self.embedder.search(query=query, k=k)
        return resultados

    def _generar_variantes(self, query: str) -> list[str]:
        """
        Genera variantes de una query para el "did you mean".

        Estrategia:
        1. Correccion con diccionario general (mas agresivo que el vocabulario).
        2. Palabras del vocabulario de eventos similares a las de la query
           (usando difflib).
        """
        variantes: list[str] = []

        # Variante 1: correccion con diccionario general
        if self.corrector is not None:
            try:
                import re
                tokens = re.findall(r"[\wáéíóúñÁÉÍÓÚÑ]+", query.lower())
                corregidos: list[str] = []
                for token in tokens:
                    if token in self.corrector.vocabulario:
                        corregidos.append(token)
                        continue
                    cands = self.corrector.spell.candidates(token)
                    if cands:
                        mejor = max(
                            cands,
                            key=lambda c: self.corrector.spell.word_frequency[c],
                        )
                        corregidos.append(mejor)
                    else:
                        corregidos.append(token)
                variante = " ".join(corregidos)
                if variante != query and variante not in variantes:
                    variantes.append(variante)
            except Exception:
                pass

        # Variante 2: palabras del vocabulario similares (difflib)
        if self.corrector is not None and self.corrector.vocabulario:
            try:
                import difflib
                vocab = list(self.corrector.vocabulario)
                tokens = query.lower().split()
                for token in tokens:
                    if len(token) < 4:
                        continue
                    matches = difflib.get_close_matches(
                        token, vocab, n=3, cutoff=0.7
                    )
                    for m in matches:
                        variante = query.replace(token, m)
                        if variante != query and variante not in variantes:
                            variantes.append(variante)
            except Exception:
                pass

        return variantes[:5]

    def _handle_recargar(self, msg: Mensaje) -> None:
        try:
            self.logger.info("Recargando embedder...")
            self._ready = False
            self.setup()
            self._responder(msg, "recarga_completada", {"ok": True})
        except Exception as e:
            self.logger.error(f"Error recargando: {e}")
            self._responder(msg, "recarga_completada", {"ok": False, "error": str(e)})

    def _handle_stats(self, msg: Mensaje) -> None:
        payload = {
            "num_eventos": self.embedder.num_events if self.embedder else 0,
            "num_shards": self.embedder.num_shards if self.embedder else 0,
            "ready": self.ready,
            "corrector_disponible": self.corrector is not None,
        }
        self._responder(msg, "stats_buscador", payload)

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def _responder(self, msg: Mensaje, tipo: str, payload: dict[str, Any]) -> None:
        destino = msg.payload.get("respuesta_a")
        if destino:
            self.enviar(destino, tipo, payload)
        else:
            self.logger.warning(f"Sin respuesta_a, no puedo responder {tipo}")

    @staticmethod
    def _limpiar_evento(ev: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in ev.items() if not k.startswith("_")}
