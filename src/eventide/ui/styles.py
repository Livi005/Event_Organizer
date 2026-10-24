"""CSS y estilos globales para la UI de Eventide.

Soporta tema claro y oscuro con CSS variables. Todo el CSS usa var(--ev-*)
para que cambiar de tema solo requiera cambiar las variables.
"""

# =============================================================
# VARIABLES DE TEMA CLARO
# =============================================================

LIGHT_VARS = """
:root {
    --ev-primary: #7c5cff;
    --ev-secondary: #5b8def;
    --ev-accent: #ec5fa8;
    --ev-gradient: linear-gradient(135deg, #7c5cff 0%, #5b8def 50%, #ec5fa8 100%);
    --ev-gradient-soft: linear-gradient(135deg, #f0ebff 0%, #eaf2ff 50%, #ffeef7 100%);
    --ev-sidebar-gradient: linear-gradient(90deg, #f4efff 0%, #eaf2ff 50%, #ffeef7 100%);
    --ev-bg: #ffffff;
    --ev-bg-soft: #f8f6ff;
    --ev-bg-lavender: #f4efff;
    --ev-text: #1a1a2e;
    --ev-text-soft: #4a4a6a;
    --ev-text-muted: #8a8aa3;
    --ev-border: #e8e4f5;
    --ev-success: #4caf7d;
    --ev-danger: #e94f6a;
    --ev-shadow-sm: 0 2px 8px rgba(124, 92, 255, 0.08);
    --ev-shadow-md: 0 6px 24px rgba(124, 92, 255, 0.12);
    --ev-shadow-lg: 0 12px 40px rgba(124, 92, 255, 0.18);
    --ev-input-bg: #ffffff;
    --ev-dropdown-bg: #ffffff;
    --ev-dropdown-hover: #f0ebff;
    --ev-score-bg: linear-gradient(135deg, #7c5cff 0%, #5b8def 100%);
    --ev-score-neg: linear-gradient(135deg, #ec5fa8 0%, #e94f6a 100%);
}
"""

# =============================================================
# VARIABLES DE TEMA OSCURO
# =============================================================

DARK_VARS = """
:root {
    --ev-primary: #9b85ff;
    --ev-secondary: #7ba6ff;
    --ev-accent: #ff7ab8;
    --ev-gradient: linear-gradient(135deg, #9b85ff 0%, #7ba6ff 50%, #ff7ab8 100%);
    --ev-gradient-soft: linear-gradient(135deg, #2a2244 0%, #1f2a44 50%, #3a1f38 100%);
    --ev-sidebar-gradient: linear-gradient(90deg, #2a2244 0%, #1f2a44 50%, #3a1f38 100%);
    --ev-bg: #0f0f1a;
    --ev-bg-soft: #1a1a2e;
    --ev-bg-lavender: #2a2440;
    --ev-text: #e8e8f0;
    --ev-text-soft: #b8b8c8;
    --ev-text-muted: #8888a0;
    --ev-border: #2a2a40;
    --ev-success: #5fd89a;
    --ev-danger: #ff6b85;
    --ev-shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
    --ev-shadow-md: 0 6px 24px rgba(0, 0, 0, 0.4);
    --ev-shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.5);
    --ev-input-bg: #1a1a2e;
    --ev-dropdown-bg: #1a1a2e;
    --ev-dropdown-hover: #2a2440;
    --ev-score-bg: linear-gradient(135deg, #9b85ff 0%, #7ba6ff 100%);
    --ev-score-neg: linear-gradient(135deg, #ff7ab8 0%, #ff6b85 100%);
}
"""

# =============================================================
# CSS BASE (usa las variables)
# =============================================================

BASE_CSS = """
<style>
/* ============================================================
   FORZAR TEMA EN TODA LA APP
   ============================================================ */
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    color: var(--ev-text) !important;
}

.stApp {
    background: var(--ev-bg) !important;
}

.stMarkdown, .stText, p, span, div, label, h1, h2, h3, h4, h5, h6 {
    color: var(--ev-text);
}

/* ============================================================
   INPUTS
   ============================================================ */
input, textarea,
.stTextInput input,
.stSelectbox div[data-baseweb="select"] > div {
    color: var(--ev-text) !important;
    background-color: var(--ev-input-bg) !important;
    border-color: var(--ev-border) !important;
}

input::placeholder, textarea::placeholder {
    color: var(--ev-text-muted) !important;
}

input:focus, textarea:focus {
    border-color: var(--ev-primary) !important;
    box-shadow: 0 0 0 3px rgba(124, 92, 255, 0.15) !important;
}

/* ============================================================
   DROPDOWN (opciones del selectbox) — CRITICO
   ============================================================ */
div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
div[data-baseweb="menu"],
div[data-baseweb="menu"] *,
ul[role="listbox"],
ul[role="listbox"] *,
li[role="option"],
li[role="option"] *,
div[role="option"] {
    background-color: var(--ev-dropdown-bg) !important;
    color: var(--ev-text) !important;
}

li[role="option"]:hover,
div[role="option"]:hover,
li[role="option"][aria-selected="true"] {
    background-color: var(--ev-dropdown-hover) !important;
    color: var(--ev-text) !important;
}

/* ============================================================
   HEADER
   ============================================================ */
.main-header {
    background: var(--ev-gradient);
    padding: 2.2rem 2.4rem;
    border-radius: 20px;
    color: #ffffff !important;
    margin-bottom: 2rem;
    box-shadow: var(--ev-shadow-lg);
    position: relative;
    overflow: hidden;
}

.main-header::before {
    content: "";
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}

.main-header h1 {
    margin: 0;
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.8px;
    color: #ffffff !important;
    position: relative;
    z-index: 1;
}

.main-header p {
    margin: 0.6rem 0 0 0;
    font-size: 1.08rem;
    opacity: 0.95;
    color: #ffffff !important;
    position: relative;
    z-index: 1;
}

/* ============================================================
   TARJETAS DE EVENTOS
   ============================================================ */
.event-card {
    background: var(--ev-bg) !important;
    border-radius: 16px;
    padding: 1.3rem 1.6rem;
    margin-bottom: 1rem;
    border-left: 5px solid var(--ev-primary);
    border-top: 1px solid var(--ev-border);
    border-right: 1px solid var(--ev-border);
    border-bottom: 1px solid var(--ev-border);
    box-shadow: var(--ev-shadow-sm);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.event-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--ev-shadow-md);
    border-left-color: var(--ev-accent);
}

.event-card h3 {
    margin: 0 0 0.6rem 0;
    color: var(--ev-text) !important;
    font-size: 1.15rem;
    font-weight: 600;
}

.event-card .meta {
    color: var(--ev-text-soft) !important;
    font-size: 0.9rem;
    margin: 0.35rem 0;
}

.event-card .badge {
    display: inline-block;
    padding: 0.25rem 0.7rem;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    margin-right: 0.4rem;
    margin-top: 0.6rem;
    background: var(--ev-bg-lavender);
    color: var(--ev-primary) !important;
}

.event-card .badge-category {
    background: var(--ev-bg-lavender);
    color: var(--ev-primary) !important;
}

.event-card .badge-score {
    background: var(--ev-bg-lavender);
    color: var(--ev-success) !important;
    font-weight: 600;
}

/* ============================================================
   NARRACION
   ============================================================ */
.narration-box {
    background: var(--ev-gradient-soft);
    border-radius: 16px;
    padding: 1.6rem 1.9rem;
    border-left: 5px solid var(--ev-accent);
    margin-bottom: 1.5rem;
    font-size: 1.02rem;
    line-height: 1.75;
    white-space: pre-wrap;
    box-shadow: var(--ev-shadow-sm);
    color: var(--ev-text) !important;
}

/* ============================================================
   AGENDA
   ============================================================ */
.agenda-item {
    background: var(--ev-bg) !important;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    border-left: 5px solid var(--ev-success);
    border-top: 1px solid var(--ev-border);
    border-right: 1px solid var(--ev-border);
    border-bottom: 1px solid var(--ev-border);
    box-shadow: var(--ev-shadow-sm);
    transition: all 0.2s;
}

.agenda-item:hover {
    transform: translateY(-2px);
    box-shadow: var(--ev-shadow-md);
}

.agenda-item .num {
    display: inline-block;
    background: var(--ev-gradient);
    color: #ffffff !important;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    text-align: center;
    line-height: 26px;
    font-size: 0.85rem;
    font-weight: 700;
    margin-right: 0.6rem;
    box-shadow: 0 2px 6px rgba(124, 92, 255, 0.35);
}

.agenda-item .title {
    font-weight: 600;
    color: var(--ev-text) !important;
    font-size: 1.05rem;
}

.agenda-item .meta {
    color: var(--ev-text-soft) !important;
    font-size: 0.88rem;
    margin-top: 0.35rem;
    padding-left: 34px;
}

/* ============================================================
   SCORE
   ============================================================ */
.score-badge {
    display: inline-block;
    background: var(--ev-score-bg);
    color: #ffffff !important;
    padding: 0.55rem 1.1rem;
    border-radius: 24px;
    font-weight: 700;
    font-size: 0.98rem;
    box-shadow: 0 4px 14px rgba(124, 92, 255, 0.35);
    letter-spacing: 0.3px;
}

.score-badge.negative {
    background: var(--ev-score-neg);
    box-shadow: 0 4px 14px rgba(236, 95, 168, 0.35);
    color: #ffffff !important;
}

/* ============================================================
   BOTONES
   ============================================================ */
.stButton > button {
    border-radius: 12px;
    font-weight: 600;
    padding: 0.6rem 1.3rem;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    border: none;
}

.stButton > button[kind="primary"] {
    background: var(--ev-gradient);
    color: #ffffff !important;
    box-shadow: 0 4px 14px rgba(124, 92, 255, 0.35);
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(124, 92, 255, 0.45);
}

.stButton > button[kind="secondary"] {
    background: var(--ev-bg-lavender);
    color: var(--ev-text) !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
}

/* ============================================================
   SIDEBAR con gradiente horizontal
   ============================================================ */
section[data-testid="stSidebar"] {
    background: var(--ev-sidebar-gradient) !important;
    border-right: 1px solid var(--ev-border);
}

section[data-testid="stSidebar"] * {
    color: var(--ev-text) !important;
}

section[data-testid="stSidebar"] h3 {
    color: var(--ev-primary) !important;
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-top: 1rem;
}

/* ============================================================
   HEADINGS
   ============================================================ */
h1, h2, h3, h4 {
    color: var(--ev-text) !important;
}

h3 {
    font-weight: 700;
    letter-spacing: -0.3px;
}

/* ============================================================
   DIVIDER
   ============================================================ */
hr {
    margin: 1.5rem 0;
    border: none;
    border-top: 1px solid var(--ev-border);
}

/* ============================================================
   EMPTY STATE
   ============================================================ */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--ev-text-muted) !important;
    background: var(--ev-bg-soft);
    border-radius: 16px;
    border: 1px dashed var(--ev-border);
}

.empty-state .icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
}

.empty-state p {
    color: var(--ev-text-muted) !important;
    font-size: 0.95rem;
}

/* ============================================================
   SPINNER
   ============================================================ */
.stSpinner > div {
    border-top-color: var(--ev-primary) !important;
}

/* ============================================================
   ALERTS
   ============================================================ */
.stAlert {
    border-radius: 12px;
    border-left: 4px solid var(--ev-primary);
}

/* ============================================================
   CODE BLOCKS (para la API URL)
   ============================================================ */
code {
    background: var(--ev-bg-lavender) !important;
    color: var(--ev-primary) !important;
    padding: 0.15rem 0.4rem;
    border-radius: 6px;
    font-size: 0.85rem;
}

/* ============================================================
   SCROLLBAR
   ============================================================ */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: var(--ev-bg-soft);
}

::-webkit-scrollbar-thumb {
    background: linear-gradient(135deg, #d0c4ff 0%, #c4d4ff 100%);
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--ev-gradient);
}
</style>
"""


def get_css(theme: str = "light") -> str:
    """
    Devuelve el CSS completo segun el tema.

    Args:
        theme: "light" o "dark".
    """
    variables = DARK_VARS if theme == "dark" else LIGHT_VARS
    return f"<style>{variables}</style>\n{BASE_CSS}"
