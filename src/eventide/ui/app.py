"""
Interfaz de usuario principal de Eventide (Streamlit).

Uso:
    streamlit run src/eventide/ui/app.py
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

# Ignorar proxies corporativos para localhost
os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(var, None)

import requests
import streamlit as st

from eventide.ui.components import (
    render_agenda_item,
    render_empty_state,
    render_evento_card,
    render_header,
    render_narracion,
    render_score,
)
from eventide.ui.styles import get_css


API_BASE = os.environ.get("EVENTIDE_API_URL", "http://localhost:8502")
PAGE_TITLE = "Eventide — Tu asistente de planes"
PAGE_ICON = "🎫"


def init_session_state() -> None:
    defaults = {
        "eventos_encontrados": [],
        "agenda_generada": [],
        "narracion": "",
        "score_agenda": 0.0,
        "busqueda_realizada": False,
        "cargando": False,
        "tema": "light",
        "query_corregida": None,
        "sugerencias": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_data(ttl=300)
def cargar_ciudades() -> list[str]:
    try:
        r = requests.get(f"{API_BASE}/api/v1/ciudades", timeout=10)
        if r.status_code == 200:
            return r.json().get("ciudades", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=300)
def cargar_categorias() -> list[str]:
    try:
        r = requests.get(f"{API_BASE}/api/v1/categorias", timeout=10)
        if r.status_code == 200:
            return r.json().get("categorias", [])
    except Exception:
        pass
    return []


def verificar_api() -> bool:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def api_buscar(query, ciudad, categoria, k=20):
    r = requests.post(
        f"{API_BASE}/api/v1/buscar",
        json={
            "query": query,
            "ciudad": ciudad or None,
            "categoria": categoria or None,
            "k": k,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def api_agenda(pool, preferencias, cantidad=5, algoritmo="sa"):
    r = requests.post(
        f"{API_BASE}/api/v1/agenda",
        json={
            "pool": pool,
            "preferencias": preferencias,
            "cantidad": cantidad,
            "algoritmo": algoritmo,
            "seed": 42,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def api_narrar(agenda, preferencias, query_original=None):
    r = requests.post(
        f"{API_BASE}/api/v1/narrar",
        json={
            "agenda": agenda,
            "preferencias": preferencias,
            "query_original": query_original,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def _evento_en_rango(ev: dict, hoy: datetime, fecha_fin: datetime) -> bool:
    """True si el evento esta dentro del rango [hoy, fecha_fin]."""
    start_raw = ev.get("temporal_info", {}).get("start")
    if not start_raw:
        return False
    try:
        start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        return hoy.date() <= start.date() <= fecha_fin.date()
    except (ValueError, AttributeError, TypeError):
        return False


def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()
    st.markdown(get_css(st.session_state.tema), unsafe_allow_html=True)
    render_header()

    if not verificar_api():
        st.error(
            f"❌ No se pudo conectar con la API en `{API_BASE}`.\n\n"
            "Asegurate de que este corriendo:\n\n"
            "```bash\neventide serve\n```"
        )
        st.stop()

    # ========== SIDEBAR ==========
    with st.sidebar:
        # Toggle de tema
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            icono = "☀️" if st.session_state.tema == "dark" else "🌙"
            if st.button(icono, use_container_width=True, key="btn_tema"):
                st.session_state.tema = (
                    "light" if st.session_state.tema == "dark" else "dark"
                )
                st.rerun()
        with col_t2:
            nombre_tema = "Oscuro" if st.session_state.tema == "dark" else "Claro"
            st.markdown(
                f"<div style='padding-top:0.5rem;font-weight:600;"
                f"color:var(--ev-primary)'>Tema {nombre_tema}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("### 🔍 Filtros")

        ciudades = cargar_ciudades()
        categorias = cargar_categorias()

        ciudad = st.selectbox(
            "Ciudad",
            options=[""] + ciudades,
            format_func=lambda x: x if x else "(cualquiera)",
            key="ciudad_select",
        )
        categoria = st.selectbox(
            "Categoria",
            options=[""] + categorias,
            format_func=lambda x: x if x else "(cualquiera)",
            key="categoria_select",
        )

        rango_dias = st.select_slider(
            "Rango temporal",
            options=[7, 14, 30, 90, 180, 365],
            value=30,
            format_func=lambda x: {
                7: "1 semana",
                14: "2 semanas",
                30: "1 mes",
                90: "3 meses",
                180: "6 meses",
                365: "1 ano",
            }[x],
            key="rango_dias_select",
        )

        # Mostrar fecha fin del rango
        fecha_fin_rango = datetime.now() + timedelta(days=rango_dias)
        st.caption(
            f"📅 Desde hoy hasta el "
            f"{fecha_fin_rango.strftime('%d %b %Y')}"
        )

        cantidad_agenda = st.slider(
            "N. eventos en la agenda",
            min_value=3, max_value=8, value=5,
            key="cantidad_agenda",
        )
        algoritmo = st.selectbox(
            "Algoritmo de optimizacion",
            options=["sa", "hc", "random"],
            format_func=lambda x: {
                "sa": "Simulated Annealing (mejor)",
                "hc": "Hill Climbing (rapido)",
                "random": "Random (baseline)",
            }[x],
            key="algoritmo_select",
        )

        st.markdown("---")
        st.markdown("### ℹ️ Estado")
        st.markdown(f"- API: `{API_BASE}`")
        st.markdown(f"- Ciudades: {len(ciudades)}")
        st.markdown(f"- Categorias: {len(categorias)}")

    # ========== BUSQUEDA ==========
    st.markdown("### ¿Que plan buscas?")
    col1, col2 = st.columns([4, 1])

    with col1:
        query = st.text_input(
            "Describe lo que te apetece",
            placeholder="Ej: concierto de musica en vivo, festival al aire libre...",
            key="query_input",
            label_visibility="collapsed",
        )
    with col2:
        buscar_btn = st.button("🔍 Buscar", use_container_width=True, type="primary")

    if buscar_btn and query.strip():
        st.session_state.cargando = True
        st.session_state.busqueda_realizada = True

        with st.spinner("Buscando eventos..."):
            try:
                data = api_buscar(
                    query=query,
                    ciudad=ciudad,
                    categoria=categoria,
                    k=50,  # mas resultados para luego filtrar por fecha
                )
                st.session_state.eventos_encontrados = data.get("resultados", [])
                st.session_state.query_corregida = data.get("query_corregida")
                st.session_state.sugerencias = data.get("sugerencias", [])
            except Exception as e:
                st.error(f"❌ Error en la busqueda: {e}")
                st.session_state.eventos_encontrados = []
                st.session_state.query_corregida = None
                st.session_state.sugerencias = []

        # ---- FILTRO DURO POR FECHA ----
        eventos_todos = st.session_state.eventos_encontrados
        hoy = datetime.now()
        fecha_fin_filtro = hoy + timedelta(days=rango_dias)

        eventos_en_rango = [
            ev for ev in eventos_todos
            if _evento_en_rango(ev, hoy, fecha_fin_filtro)
        ]

        # Actualizar los eventos encontrados a solo los del rango
        st.session_state.eventos_encontrados = eventos_en_rango

        if len(eventos_en_rango) < cantidad_agenda:
            st.session_state.agenda_generada = []
            st.session_state.narracion = ""
            st.session_state.cargando = False
            if eventos_todos:
                st.warning(
                    f"⚠️ Solo hay {len(eventos_en_rango)} eventos en los "
                    f"proximos {rango_dias} dias. Amplia el rango temporal "
                    f"o cambia los filtros."
                )
            # No salimos, dejamos que se muestren los eventos encontrados
        else:
            # Generar agenda
            with st.spinner("Optimizando agenda..."):
                try:
                    preferencias = {
                        "location": ciudad or None,
                        "categories": [categoria] if categoria else [],
                        "available_dates": (
                            hoy.isoformat(),
                            fecha_fin_filtro.isoformat(),
                        ),
                        "duracion_maxima": 300,
                        "velocidad_kmh": 30,
                    }
                    data_ag = api_agenda(
                        pool=eventos_en_rango,
                        preferencias=preferencias,
                        cantidad=cantidad_agenda,
                        algoritmo=algoritmo,
                    )
                    st.session_state.agenda_generada = data_ag.get("agenda", [])
                    st.session_state.score_agenda = data_ag.get("score", 0.0)
                except Exception as e:
                    st.error(f"❌ Error generando agenda: {e}")
                    st.session_state.agenda_generada = []

            # Narracion
            if st.session_state.agenda_generada:
                with st.spinner("Preparando recomendacion..."):
                    try:
                        data_narr = api_narrar(
                            agenda=st.session_state.agenda_generada,
                            preferencias=preferencias,
                            query_original=query,
                        )
                        st.session_state.narracion = data_narr.get("texto", "")
                    except Exception as e:
                        st.session_state.narracion = (
                            f"(No se pudo generar la narracion: {e})"
                        )

        st.session_state.cargando = False

    # Renderizar resultados
    render_resultados(rango_dias)


def render_resultados(rango_dias: int = 30) -> None:
    if not st.session_state.busqueda_realizada:
        render_empty_state(
            "Escribe lo que buscas y pulsa Buscar. Te armare una agenda a medida.",
            "🎯",
        )
        return

    # Aviso de correccion ortografica
    if st.session_state.query_corregida and st.session_state.sugerencias:
        palabras = ", ".join(
            f'"{s["palabra_original"]}" → "{s["sugerencia"]}"'
            for s in st.session_state.sugerencias
        )
        st.info(
            f"💡 Corregi tu busqueda: {palabras}. "
            f"Se busco como: *{st.session_state.query_corregida}*"
        )
    elif st.session_state.query_corregida:
        st.info(
            f"💡 Interprete tu busqueda como: "
            f"*{st.session_state.query_corregida}*"
        )

    eventos = st.session_state.eventos_encontrados
    agenda = st.session_state.agenda_generada
    narracion = st.session_state.narracion
    score = st.session_state.score_agenda

    col_izq, col_der = st.columns([2, 1], gap="large")

    with col_izq:
        if not eventos:
            render_empty_state(
                f"No encontre eventos en los proximos {rango_dias} dias. "
                f"Prueba a ampliar el rango o cambiar filtros.",
                "😕",
            )
            return

        st.markdown(
            f"### 📋 Eventos encontrados ({len(eventos)}) · "
            f"en los proximos {rango_dias} dias"
        )

        if narracion:
            st.markdown("### 💬 Tu recomendacion personalizada")
            render_narracion(narracion)

        st.markdown("---")
        for ev in eventos:
            render_evento_card(ev, mostrar_score=True)

    with col_der:
        st.markdown("### 🗓️ Tu agenda")
        if agenda:
            render_score(score)
            st.markdown("")
            for i, ev in enumerate(agenda, 1):
                render_agenda_item(ev, i)
        else:
            render_empty_state(
                f"Necesito al menos 5 eventos en los proximos "
                f"{rango_dias} dias para armar una agenda.",
                "📅",
            )


if __name__ == "__main__":
    main()