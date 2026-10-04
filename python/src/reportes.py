"""
reportes.py
===========
Generación de reportes HTML autocontenidos a partir de un backtest.

Uso:
----
    from src.reportes import generar_reporte

    ruta = generar_reporte(
        resultado=resultado,
        config={
            "exchange": "binance",
            "simbolo": "BTC/USDT",
            "timeframe": "4h",
            "desde": "2024-01-01",
            "hasta": "2024-12-31",
            "estrategia": "cruce_sma",
            "params_estrategia": {"sma_rapida": 20, "sma_lenta": 50},
            "riesgo": {"modo": "porcentaje", "sl_pct": 2.0, "tp_pct": 4.0},
            "costes": {"capital": 10000, "comision": 0.1, "slippage": 0.05},
        },
        df=df,
        ruta_salida=Path("data/resultados/reporte.html"),
    )
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.backtest import ResultadoBacktest


# ============================================================================
# Construcción de gráficos
# ============================================================================
def _grafico_precio_trades(df: pd.DataFrame, resultado: ResultadoBacktest) -> go.Figure:
    """Velas + marcadores de entrada/salida + volumen."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("Precio y operaciones", "Volumen"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Precio",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    if resultado.trades:
        longs = [t for t in resultado.trades if t.direccion == "long"]
        shorts = [t for t in resultado.trades if t.direccion == "short"]

        if longs:
            fig.add_trace(
                go.Scatter(
                    x=[t.entrada_fecha for t in longs],
                    y=[t.entrada_precio for t in longs],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=11, color="#26a69a",
                                line=dict(color="white", width=1)),
                    name="Entrada Long",
                ),
                row=1, col=1,
            )
        if shorts:
            fig.add_trace(
                go.Scatter(
                    x=[t.entrada_fecha for t in shorts],
                    y=[t.entrada_precio for t in shorts],
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=11, color="#ef5350",
                                line=dict(color="white", width=1)),
                    name="Entrada Short",
                ),
                row=1, col=1,
            )

        fig.add_trace(
            go.Scatter(
                x=[t.salida_fecha for t in resultado.trades],
                y=[t.salida_precio for t in resultado.trades],
                mode="markers",
                marker=dict(
                    symbol="x", size=9,
                    color=["#26a69a" if t.pnl > 0 else "#ef5350" for t in resultado.trades],
                ),
                name="Salida",
            ),
            row=1, col=1,
        )

    # Volumen
    colores_vol = ["#26a69a" if c >= o else "#ef5350"
                   for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], marker_color=colores_vol, name="Volumen"),
        row=2, col=1,
    )

    fig.update_layout(
        height=650,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        template="plotly_dark",
        margin=dict(l=40, r=20, t=60, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#2a2a2a")
    fig.update_yaxes(showgrid=True, gridcolor="#2a2a2a")
    return fig


def _grafico_equity(resultado: ResultadoBacktest, capital_inicial: float) -> go.Figure:
    """Curva de equity + drawdown."""
    equity = resultado.equity_curve

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
        subplot_titles=("Curva de equity", "Drawdown"),
    )

    # Equity
    fig.add_trace(
        go.Scatter(
            x=equity.index, y=equity.values,
            mode="lines", fill="tozeroy",
            line=dict(color="#42a5f5", width=2),
            name="Equity",
        ),
        row=1, col=1,
    )
    fig.add_hline(
        y=capital_inicial, line_dash="dash", line_color="#888",
        annotation_text="Capital inicial",
        row=1, col=1,
    )

    # Drawdown
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max * 100

    fig.add_trace(
        go.Scatter(
            x=dd.index, y=dd.values,
            mode="lines", fill="tozeroy",
            line=dict(color="#ef5350", width=2),
            name="Drawdown",
        ),
        row=2, col=1,
    )

    fig.update_layout(
        height=600,
        showlegend=False,
        template="plotly_dark",
        margin=dict(l=40, r=20, t=60, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#2a2a2a")
    fig.update_yaxes(showgrid=True, gridcolor="#2a2a2a")
    return fig


# ============================================================================
# Tabla HTML de trades
# ============================================================================
def _tabla_trades_html(trades: list) -> str:
    """Genera una tabla HTML con todos los trades."""
    if not trades:
        return "<p><em>No se generaron operaciones.</em></p>"

    filas = []
    for i, t in enumerate(trades, 1):
        clase = "ganador" if t.pnl > 0 else "perdedor"
        filas.append(f"""
            <tr class="{clase}">
                <td>{i}</td>
                <td>{t.direccion.upper()}</td>
                <td>{t.entrada_fecha.strftime('%Y-%m-%d %H:%M')}</td>
                <td class="num">${t.entrada_precio:,.2f}</td>
                <td>{t.salida_fecha.strftime('%Y-%m-%d %H:%M') if t.salida_fecha else '—'}</td>
                <td class="num">${t.salida_precio:,.2f}</td>
                <td>{t.motivo_salida}</td>
                <td class="num {'pos' if t.pnl > 0 else 'neg'}">${t.pnl:+,.2f}</td>
                <td class="num {'pos' if t.pnl > 0 else 'neg'}">{t.pnl_pct:+.2f}%</td>
                <td>{t.duracion_velas}</td>
            </tr>
        """)

    return f"""
    <table class="trades">
        <thead>
            <tr>
                <th>#</th>
                <th>Dir</th>
                <th>Entrada</th>
                <th>Precio</th>
                <th>Salida</th>
                <th>Precio</th>
                <th>Motivo</th>
                <th>PnL</th>
                <th>PnL %</th>
                <th>Velas</th>
            </tr>
        </thead>
        <tbody>
            {''.join(filas)}
        </tbody>
    </table>
    """


# ============================================================================
# Plantilla HTML
# ============================================================================
_CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #121212;
    color: #e0e0e0;
    margin: 0;
    padding: 2rem;
    line-height: 1.5;
}
.container { max-width: 1400px; margin: 0 auto; }
h1 { color: #42a5f5; margin-bottom: 0.25rem; font-size: 1.8rem; }
h2 { color: #90caf9; margin-top: 2rem; border-bottom: 1px solid #2a2a2a; padding-bottom: 0.5rem; font-size: 1.3rem; }
.subtitulo { color: #888; margin-top: 0; font-size: 0.95rem; }
.metricas {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin: 1.5rem 0;
}
.metrica {
    background: #1e1e1e;
    border-radius: 8px;
    padding: 1rem;
    border-left: 3px solid #42a5f5;
}
.metrica .label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
.metrica .valor { font-size: 1.4rem; font-weight: 600; margin-top: 0.25rem; }
.metrica .valor.pos { color: #26a69a; }
.metrica .valor.neg { color: #ef5350; }
.config {
    background: #1e1e1e;
    border-radius: 8px;
    padding: 1.5rem;
    margin: 1.5rem 0;
}
.config-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
}
.config-item { font-size: 0.9rem; }
.config-item strong { color: #90caf9; }
table.trades {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.85rem;
    background: #1e1e1e;
    border-radius: 8px;
    overflow: hidden;
}
table.trades th {
    background: #2a2a2a;
    padding: 0.6rem 0.8rem;
    text-align: left;
    font-weight: 600;
    color: #90caf9;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
table.trades td {
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #2a2a2a;
}
table.trades tr:hover { background: #252525; }
table.trades td.num { text-align: right; font-family: "SF Mono", Consolas, monospace; }
table.trades td.pos { color: #26a69a; font-weight: 600; }
table.trades td.neg { color: #ef5350; font-weight: 600; }
.ganador { border-left: 3px solid #26a69a; }
.perdedor { border-left: 3px solid #ef5350; }
.footer {
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid #2a2a2a;
    color: #666;
    font-size: 0.85rem;
    text-align: center;
}
"""


def _tarjeta_metrica(label: str, valor: str, clase: str = "") -> str:
    """Genera una tarjeta de métrica."""
    return f"""
    <div class="metrica">
        <div class="label">{label}</div>
        <div class="valor {clase}">{valor}</div>
    </div>
    """


# ============================================================================
# Función principal
# ============================================================================
def generar_reporte(
    resultado: ResultadoBacktest,
    config: dict[str, Any],
    df: pd.DataFrame | None = None,
    ruta_salida: str | Path | None = None,
    incluir_graficos: bool = True,
) -> Path:
    """
    Genera un reporte HTML autocontenido del backtest.

    Parámetros
    ----------
    resultado : ResultadoBacktest
    config : dict
        Configuración usada (exchange, simbolo, timeframe, etc.).
    df : DataFrame, opcional
        Datos OHLCV originales. Si se pasa, se incluye el gráfico de precio.
    ruta_salida : str | Path, opcional
        Ruta donde guardar el HTML. Si es None, se autogenera.
    incluir_graficos : bool
        Si False, omite los gráficos Plotly.

    Devuelve
    --------
    Path al archivo HTML generado.
    """
    m = resultado.metricas
    cap_inicial = resultado.capital_inicial
    retorno = m.get("retorno_total_pct", 0)
    clase_retorno = "pos" if retorno > 0 else "neg" if retorno < 0 else ""

    # --- Ruta por defecto ---
    if ruta_salida is None:
        raiz = Path(__file__).resolve().parents[2]
        simbolo_limpio = config.get("simbolo", "unknown").replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_salida = (
            raiz / "data" / "resultados"
            / f"reporte_{simbolo_limpio}_{config.get('timeframe', 'x')}_{timestamp}.html"
        )
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    # --- Tarjetas de métricas ---
    tarjetas = "".join([
        _tarjeta_metrica("Retorno total", f"{retorno:+.2f}%", clase_retorno),
        _tarjeta_metrica("Capital final", f"${m.get('capital_final', 0):,.0f}"),
        _tarjeta_metrica("CAGR", f"{m.get('cagr_pct', 0):+.2f}%"),
        _tarjeta_metrica("Nº trades", str(m.get("num_trades", 0))),
        _tarjeta_metrica("Winrate", f"{m.get('winrate_pct', 0):.1f}%"),
        _tarjeta_metrica("Profit Factor", str(m.get("profit_factor", "—"))),
        _tarjeta_metrica("Max DD", f"{m.get('max_drawdown_pct', 0):.2f}%", "neg"),
        _tarjeta_metrica("Sharpe", f"{m.get('sharpe', 0):.2f}"),
        _tarjeta_metrica("Sortino", f"{m.get('sortino', 0):.2f}"),
        _tarjeta_metrica("Expectancy", f"${m.get('expectancy', 0):,.2f}"),
        _tarjeta_metrica("Avg Win", f"${m.get('avg_win', 0):,.2f}", "pos"),
        _tarjeta_metrica("Avg Loss", f"${m.get('avg_loss', 0):,.2f}", "neg"),
    ])

    # --- Configuración ---
    riesgo = config.get("riesgo", {})
    costes = config.get("costes", {})
    params = config.get("params_estrategia", {})

    config_html = f"""
    <div class="config">
        <div class="config-grid">
            <div class="config-item"><strong>Exchange:</strong> {config.get('exchange', '—')}</div>
            <div class="config-item"><strong>Símbolo:</strong> {config.get('simbolo', '—')}</div>
            <div class="config-item"><strong>Timeframe:</strong> {config.get('timeframe', '—')}</div>
            <div class="config-item"><strong>Desde:</strong> {config.get('desde', '—')}</div>
            <div class="config-item"><strong>Hasta:</strong> {config.get('hasta', '—')}</div>
            <div class="config-item"><strong>Estrategia:</strong> {config.get('estrategia', '—')}</div>
            <div class="config-item"><strong>Direcciones:</strong> {'Longs' if config.get('permitir_longs') else ''}{' + ' if config.get('permitir_longs') and config.get('permitir_shorts') else ''}{'Shorts' if config.get('permitir_shorts') else ''}</div>
            <div class="config-item"><strong>Modo SL/TP:</strong> {riesgo.get('modo', '—')}</div>
            <div class="config-item"><strong>Capital inicial:</strong> ${costes.get('capital', 0):,.0f}</div>
            <div class="config-item"><strong>Comisión:</strong> {costes.get('comision', 0)}%</div>
            <div class="config-item"><strong>Slippage:</strong> {costes.get('slippage', 0)}%</div>
            <div class="config-item"><strong>Parámetros:</strong> {', '.join(f'{k}={v}' for k, v in params.items()) or '—'}</div>
        </div>
    </div>
    """

    # --- Gráficos ---
    graficos_html = ""
    if incluir_graficos:
        if df is not None and len(df) > 0:
            fig_precio = _grafico_precio_trades(df, resultado)
            graficos_html += fig_precio.to_html(
                full_html=False, include_plotlyjs="cdn",
                config={"displayModeBar": True, "responsive": True},
            )

        fig_equity = _grafico_equity(resultado, cap_inicial)
        graficos_html += fig_equity.to_html(
            full_html=False, include_plotlyjs=False,
            config={"displayModeBar": True, "responsive": True},
        )

    # --- Tabla de trades ---
    tabla_html = _tabla_trades_html(resultado.trades)

    # --- HTML final ---
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Backtest — {config.get('simbolo', '')} {config.get('timeframe', '')}</title>
    <style>{_CSS}</style>
</head>
<body>
    <div class="container">
        <h1>📊 Reporte de Backtest</h1>
        <p class="subtitulo">
            {config.get('simbolo', '—')} · {config.get('timeframe', '—')} ·
            {config.get('desde', '—')} → {config.get('hasta', '—')} ·
            Estrategia: {config.get('estrategia', '—')}
        </p>

        <h2>Métricas principales</h2>
        <div class="metricas">{tarjetas}</div>

        <h2>Configuración</h2>
        {config_html}

        {'<h2>Gráficos</h2>' + graficos_html if incluir_graficos else ''}

        <h2>Operaciones ({len(resultado.trades)})</h2>
        {tabla_html}

        <div class="footer">
            Generado por <strong>estudio_criptomonedas</strong> ·
            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""

    ruta_salida.write_text(html, encoding="utf-8")
    return ruta_salida


# ============================================================================
# CLI rápida de prueba
# ============================================================================
if __name__ == "__main__":
    from rich.console import Console

    from src.data_loader import DataLoader
    from src.estrategias import obtener_estrategia
    from src.backtest import Backtest

    console = Console()

    # Config de ejemplo
    config = {
        "exchange": "binance",
        "simbolo": "BTC/USDT",
        "timeframe": "4h",
        "desde": "2024-01-01",
        "hasta": "2024-12-31",
        "estrategia": "cruce_sma",
        "params_estrategia": {"sma_rapida": 20, "sma_lenta": 50},
        "riesgo": {"modo": "porcentaje", "sl_pct": 2.0, "tp_pct": 4.0},
        "costes": {"capital": 10000, "comision": 0.1, "slippage": 0.05},
        "permitir_longs": True,
        "permitir_shorts": False,
    }

    console.print("[blue]→[/blue] Descargando datos...")
    dl = DataLoader(exchange=config["exchange"])
    df = dl.cargar(
        config["simbolo"], config["timeframe"],
        config["desde"], config["hasta"],
    )
    console.print(f"[green]✓[/green] {len(df)} velas")

    console.print("[blue]→[/blue] Ejecutando backtest...")
    est = obtener_estrategia(config["estrategia"], **config["params_estrategia"])
    bt = Backtest(
        df=df, estrategia=est,
        capital_inicial=config["costes"]["capital"],
        comision_pct=config["costes"]["comision"],
        slippage_pct=config["costes"]["slippage"],
        riesgo={**config["riesgo"], "riesgo_pct": 2.0},
        permitir_longs=config["permitir_longs"],
        permitir_shorts=config["permitir_shorts"],
    )
    resultado = bt.ejecutar()
    console.print(f"[green]✓[/green] {resultado.metricas['num_trades']} trades")

    console.print("[blue]→[/blue] Generando reporte HTML...")
    ruta = generar_reporte(resultado, config, df=df)
    console.print(f"[green]✓[/green] Reporte: [cyan]{ruta}[/cyan]")