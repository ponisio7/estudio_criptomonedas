"""
graficos.py
===========
Funciones auxiliares para construir gráficos Plotly reutilizables.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def grafico_precio_con_indicadores(
    df: pd.DataFrame,
    indicadores: list[dict] | None = None,
    titulo: str = "Precio",
    altura: int = 600,
) -> go.Figure:
    """
    Gráfico de velas con indicadores superpuestos.

    Parámetros
    ----------
    df : DataFrame con columnas OHLCV
    indicadores : lista de dicts con keys {columna, color, nombre}
    """
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Precio",
    ))

    for ind in (indicadores or []):
        col = ind.get("columna")
        if col and col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                mode="lines",
                line=dict(color=ind.get("color", "blue"), width=1.5),
                name=ind.get("nombre", col),
            ))

    fig.update_layout(
        title=titulo,
        height=altura,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def grafico_equity_con_drawdown(
    equity: pd.Series,
    capital_inicial: float,
    altura: int = 500,
) -> tuple[go.Figure, go.Figure]:
    """Devuelve (figura_equity, figura_drawdown)."""

    # Equity
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines", fill="tozeroy",
        line=dict(color="royalblue", width=2),
        name="Equity",
    ))
    fig_eq.add_hline(y=capital_inicial, line_dash="dash", line_color="gray")
    fig_eq.update_layout(
        title="Curva de equity",
        yaxis_title="Capital ($)",
        height=altura,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    # Drawdown
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max * 100

    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", line=dict(color="crimson"),
        name="Drawdown",
    ))
    fig_dd.update_layout(
        title="Drawdown (%)",
        yaxis_title="%",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig_eq, fig_dd