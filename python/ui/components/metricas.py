"""
metricas.py
===========
Componentes de visualización de métricas.
"""

from __future__ import annotations

import streamlit as st


def mostrar_metricas_principales(m: dict) -> None:
    """Fila de 6 métricas principales."""
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    col1.metric(
        "Retorno total",
        f"{m.get('retorno_total_pct', 0):+.2f}%",
    )
    col2.metric(
        "Capital final",
        f"${m.get('capital_final', 0):,.0f}",
    )
    col3.metric(
        "Nº trades",
        m.get("num_trades", 0),
    )
    col4.metric(
        "Winrate",
        f"{m.get('winrate_pct', 0):.1f}%",
    )
    col5.metric(
        "Max DD",
        f"{m.get('max_drawdown_pct', 0):.1f}%",
    )
    col6.metric(
        "Sharpe",
        f"{m.get('sharpe', 0):.2f}",
    )


def mostrar_metricas_secundarias(m: dict) -> None:
    """Fila de 4 métricas secundarias."""
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("CAGR", f"{m.get('cagr_pct', 0):+.2f}%")
    col2.metric("Profit Factor", str(m.get("profit_factor", "—")))
    col3.metric("Expectancy", f"${m.get('expectancy', 0):.2f}")
    col4.metric(
        "Duración media",
        f"{m.get('duracion_media_velas', 0):.0f} velas",
    )