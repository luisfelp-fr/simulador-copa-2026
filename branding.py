"""
Identidade visual do painel (cores e cabeçalho) — herda o estilo do HTML original.
"""
from __future__ import annotations

COLORS = {
    "primary": "#0a3a60",   # azul-escuro
    "primary_dark": "#021729",
    "secondary": "#1df2a1",  # verde-destaque
    "dark": "#1e293b",
    "light": "#f8fafc",
    "gray": "#64748b",
    "qualified": "#0f5132",  # texto verde p/ classificados
    "qualified_bg": "#e9f9f1",
}


def header_html() -> str:
    """Cabeçalho no estilo do painel original (faixa azul com gradiente)."""
    return (
        f"<div style='background:linear-gradient(135deg,{COLORS['primary']},"
        f"{COLORS['primary_dark']});color:#fff;text-align:center;padding:1.6rem 1rem;"
        "border-radius:12px;margin-bottom:1rem;box-shadow:0 4px 10px rgba(0,0,0,.15)'>"
        "<div style='font-size:1.9rem;font-weight:800;line-height:1.15'>"
        "🏆 Copa do Mundo 2026</div>"
        "<div style='color:#9fb4c7;margin-top:4px;font-size:1rem'>"
        "Canadá · Estados Unidos · México — Painel de Resultados, Classificação e Simulação</div>"
        "</div>"
    )


def section_title(text: str) -> str:
    """Título de seção com a barra lateral azul do HTML original."""
    return (
        f"<h3 style='border-left:5px solid {COLORS['primary']};padding-left:10px;"
        f"color:{COLORS['primary']};margin:1.2rem 0 .6rem'>{text}</h3>"
    )


def chip(text: str, bg: str, fg: str = "#fff") -> str:
    return (f"<span style='background:{bg};color:{fg};padding:2px 8px;"
            f"border-radius:10px;font-size:.78rem;font-weight:600'>{text}</span>")
