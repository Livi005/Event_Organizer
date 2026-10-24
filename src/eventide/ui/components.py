"""Componentes reutilizables de la UI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


# =============================================================
# CONSTANTES
# =============================================================

EMOJI_CAT = {
    "concerts": "🎸",
    "festivals": "🎪",
    "theater": "🎭",
    "arts": "🎨",
    "sports": "⚽",
    "food": "🍽️",
    "technology": "💻",
    "conferences": "🎤",
    "literature": "📚",
    "wellness": "🧘",
}

MESES_ABREV = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


# =============================================================
# HELPERS
# =============================================================

def formatear_fecha_hora(iso_str: str) -> str:
    """Convierte ISO 8601 a 'DD mmm, HH:MM'."""
    if not iso_str:
        return "fecha por confirmar"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        mes = MESES_ABREV.get(dt.month, f"{dt.month:02d}")
        return f"{dt.day:02d} {mes}, {dt.hour:02d}:{dt.minute:02d}"
    except (ValueError, AttributeError, TypeError):
        return iso_str


def extraer_info_evento(ev: dict[str, Any]) -> dict[str, Any]:
    """Extrae info resumida de un evento para mostrar en tarjetas."""
    basic = ev.get("basic_info", {})
    temporal = ev.get("temporal_info", {})
    spatial = ev.get("spatial_info", {})
    classification = ev.get("classification", {})

    return {
        "titulo": basic.get("title", "Sin titulo"),
        "descripcion": basic.get("description", ""),
        "fecha_raw": temporal.get("start", ""),
        "fecha_fmt": formatear_fecha_hora(temporal.get("start", "")),
        "duracion": temporal.get("duration_minutes"),
        "venue": spatial.get("venue", {}).get("name", ""),
        "ciudad": spatial.get("area", {}).get("city", ""),
        "direccion": spatial.get("venue", {}).get("full_address", ""),
        "categoria": classification.get("primary_category", ""),
        "emoji": EMOJI_CAT.get(classification.get("primary_category", ""), "📌"),
        "score": ev.get("score", 0.0),
    }


# =============================================================
# COMPONENTES
# =============================================================

def render_header() -> None:
    """Cabecera principal."""
    st.markdown("""
        <div class="main-header">
            <h1>🎫 Eventide</h1>
            <p>Tu asistente personal de planes. Encuentra eventos y arma tu agenda ideal.</p>
        </div>
    """, unsafe_allow_html=True)


def render_narracion(texto: str) -> None:
    """Caja con la narracion del asistente."""
    st.markdown(f'<div class="narration-box">{texto}</div>', unsafe_allow_html=True)


def render_evento_card(ev: dict[str, Any], mostrar_score: bool = True) -> None:
    """Tarjeta de evento individual."""
    info = extraer_info_evento(ev)

    partes = []
    partes.append('<div class="event-card">')
    partes.append(f'<h3>{info["emoji"]} {info["titulo"]}</h3>')

    # Fecha + duracion
    meta_fecha = f'📅 {info["fecha_fmt"]}'
    if info["duracion"]:
        meta_fecha += f' · {info["duracion"]} min'
    partes.append(f'<div class="meta">{meta_fecha}</div>')

    # Venue + ciudad
    if info["venue"] or info["ciudad"]:
        meta_lugar = f'📍 {info["venue"]}' if info["venue"] else ''
        if info["ciudad"]:
            meta_lugar += f' · {info["ciudad"]}' if meta_lugar else f'📍 {info["ciudad"]}'
        partes.append(f'<div class="meta">{meta_lugar}</div>')

    # Badges
    if info["categoria"]:
        partes.append(f'<span class="badge badge-category">{info["categoria"]}</span>')
    if mostrar_score and info["score"]:
        partes.append(f'<span class="badge badge-score">score: {info["score"]:.3f}</span>')

    partes.append('</div>')
    st.markdown("".join(partes), unsafe_allow_html=True)


def render_agenda_item(ev: dict[str, Any], num: int) -> None:
    """Item de la agenda (numerado)."""
    info = extraer_info_evento(ev)

    partes = []
    partes.append('<div class="agenda-item">')
    partes.append(f'<div><span class="num">{num}</span><span class="title">{info["emoji"]} {info["titulo"]}</span></div>')
    partes.append(f'<div class="meta">📅 {info["fecha_fmt"]}</div>')
    if info["venue"]:
        partes.append(f'<div class="meta">📍 {info["venue"]} · {info["ciudad"]}</div>')
    partes.append('</div>')
    st.markdown("".join(partes), unsafe_allow_html=True)


def render_score(score: float) -> None:
    """Badge del score."""
    clase = "score-badge" if score >= 0 else "score-badge negative"
    st.markdown(
        f'<span class="{clase}">✨ Score: {score:.2f}</span>',
        unsafe_allow_html=True,
    )


def render_empty_state(mensaje: str, icono: str = "🔍") -> None:
    """Estado vacio con icono."""
    st.markdown(
        f'<div class="empty-state"><div class="icon">{icono}</div><p>{mensaje}</p></div>',
        unsafe_allow_html=True,
    )
