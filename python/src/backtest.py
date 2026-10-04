"""
backtest.py
===========
Motor de backtest vela a vela con gestión de riesgo integrada.

Uso:
----
    from src.data_loader import DataLoader
    from src.estrategias import obtener_estrategia
    from src.backtest import Backtest

    df = DataLoader().cargar("BTC/USDT", "4h", "2022-01-01", "2024-12-31")
    est = obtener_estrategia("cruce_sma", sma_rapida=20, sma_lenta=50)

    bt = Backtest(
        df=df,
        estrategia=est,
        capital_inicial=10000,
        comision_pct=0.1,
        slippage_pct=0.05,
        riesgo={"modo": "atr", "atr_mult_sl": 1.5, "atr_mult_tp": 3.0},
    )
    resultado = bt.ejecutar()
    print(resultado.metricas)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from src.estrategias import Estrategia
from src.riesgo import calcular_sl_tp, calcular_qty


# ============================================================================
# Dataclasses de resultado
# ============================================================================
@dataclass
class Trade:
    """Una operación completa."""
    entrada_fecha:  pd.Timestamp
    entrada_precio: float
    direccion:      Literal["long", "short"]
    qty:            float
    sl:             float | None
    tp:             float | None
    salida_fecha:   pd.Timestamp | None = None
    salida_precio:  float | None = None
    motivo_salida:  str = ""              # "tp", "sl", "señal_contraria", "fin"
    pnl:            float = 0.0
    pnl_pct:        float = 0.0
    comision:       float = 0.0
    duracion_velas: int = 0

    @property
    def es_ganadora(self) -> bool:
        return self.pnl > 0


@dataclass
class ResultadoBacktest:
    """Resultado completo del backtest."""
    trades:          list[Trade]
    equity_curve:    pd.Series
    metricas:        dict = field(default_factory=dict)
    capital_inicial: float = 0.0
    señales:         pd.Series | None = None      # ← NUEVO
    precios:         pd.DataFrame | None = None   # ← NUEVO (opcional, para debug)

    def resumen(self) -> str:
        """Devuelve un string con las métricas clave."""
        lineas = []
        for k, v in self.metricas.items():
            if isinstance(v, float):
                lineas.append(f"{k:.<30} {v:>12.4f}")
            else:
                lineas.append(f"{k:.<30} {v:>12}")
        return "\n".join(lineas)


# ============================================================================
# Motor de backtest
# ============================================================================
class Backtest:
    """
    Backtest vela a vela. Sin look-ahead bias:
    - La señal se evalúa al cierre de la vela t.
    - La entrada se ejecuta al open de la vela t+1.
    - El SL/TP se evalúa con el high/low de cada vela.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        estrategia: Estrategia,
        capital_inicial: float = 10_000,
        comision_pct: float = 0.1,
        slippage_pct: float = 0.05,
        riesgo: dict | None = None,
        permitir_longs: bool = True,
        permitir_shorts: bool = False,
        usar_atr: bool = True,
        atr_len: int = 14,
    ):
        self.df = df.copy()
        self.estrategia = estrategia
        self.capital_inicial = capital_inicial
        self.comision_pct = comision_pct / 100
        self.slippage_pct = slippage_pct / 100
        self.riesgo = riesgo or {
            "modo": "porcentaje",
            "sl_pct": 2.0, "tp_pct": 4.0,
            "atr_mult_sl": 1.5, "atr_mult_tp": 3.0,
        }
        self.permitir_longs = permitir_longs
        self.permitir_shorts = permitir_shorts
        self.usar_atr = usar_atr
        self.atr_len = atr_len

        # Añadir ATR si hace falta
        if usar_atr and "atr" not in self.df.columns:
            from src.indicadores import atr
            self.df["atr"] = atr(
                self.df["high"], self.df["low"], self.df["close"], atr_len
            )

        # Calcular señales
        self.df["señal"] = estrategia.generar_senales(self.df)

    # ------------------------------------------------------------------
    def ejecutar(self) -> ResultadoBacktest:
        """Recorre el DataFrame y simula las operaciones."""
        df = self.df
        trades: list[Trade] = []

        capital = self.capital_inicial
        equity = [capital]

        # Estado de posición abierta
        posicion_abierta: Trade | None = None
        señal_pendiente: int = 0  # señal generada en t, ejecutar en t+1

        for i in range(len(df)):
            fila = df.iloc[i]

            # 1) Ejecutar señal pendiente de la vela anterior
            if señal_pendiente != 0 and posicion_abierta is None:
                direccion = "long" if señal_pendiente == 1 else "short"
                precio_entrada = fila["open"]
                # Slippage: empeora el precio
                if direccion == "long":
                    precio_entrada *= (1 + self.slippage_pct)
                else:
                    precio_entrada *= (1 - self.slippage_pct)

                sl, tp = calcular_sl_tp(
                    precio_entrada=precio_entrada,
                    direccion=direccion,
                    atr_actual=fila.get("atr"),
                    modo=self.riesgo.get("modo", "porcentaje"),
                    sl_pct=self.riesgo.get("sl_pct", 2.0),
                    tp_pct=self.riesgo.get("tp_pct", 4.0),
                    atr_mult_sl=self.riesgo.get("atr_mult_sl", 1.5),
                    atr_mult_tp=self.riesgo.get("atr_mult_tp", 3.0),
                )

                qty = calcular_qty(
                    capital=capital,
                    precio_entrada=precio_entrada,
                    stop_loss=sl,
                    riesgo_pct=self.riesgo.get("riesgo_pct", 2.0),
                    modo="riesgo_fijo",
                )

                posicion_abierta = Trade(
                    entrada_fecha=df.index[i],
                    entrada_precio=precio_entrada,
                    direccion=direccion,
                    qty=qty,
                    sl=sl,
                    tp=tp,
                )
                señal_pendiente = 0

            # 2) Gestionar posición abierta con high/low de la vela
            if posicion_abierta is not None:
                trade = posicion_abierta
                salida_precio = None
                motivo = ""

                if trade.direccion == "long":
                    # Comprobar SL
                    if trade.sl is not None and fila["low"] <= trade.sl:
                        salida_precio = trade.sl
                        motivo = "sl"
                    # Comprobar TP
                    elif trade.tp is not None and fila["high"] >= trade.tp:
                        salida_precio = trade.tp
                        motivo = "tp"
                    # Señal contraria
                    elif fila["señal"] == -1:
                        salida_precio = fila["close"]
                        motivo = "señal_contraria"

                else:  # short
                    if trade.sl is not None and fila["high"] >= trade.sl:
                        salida_precio = trade.sl
                        motivo = "sl"
                    elif trade.tp is not None and fila["low"] <= trade.tp:
                        salida_precio = trade.tp
                        motivo = "tp"
                    elif fila["señal"] == 1:
                        salida_precio = fila["close"]
                        motivo = "señal_contraria"

                # Cerrar posición
                if salida_precio is not None:
                    self._cerrar_trade(trade, salida_precio, df.index[i], motivo, capital)
                    capital += trade.pnl
                    trades.append(trade)
                    posicion_abierta = None

            # 3) Registrar señal para ejecutar en la siguiente vela
            señal = int(fila["señal"])
            if posicion_abierta is None:
                if señal == 1 and self.permitir_longs:
                    señal_pendiente = 1
                elif señal == -1 and self.permitir_shorts:
                    señal_pendiente = -1

            # 4) Registrar equity
            equity_actual = capital
            if posicion_abierta is not None:
                equity_actual += self._pnl_no_realizado(posicion_abierta, fila["close"])
            equity.append(equity_actual)

        # Cerrar posición abierta al final
        if posicion_abierta is not None:
            ultima = df.iloc[-1]
            self._cerrar_trade(posicion_abierta, ultima["close"], df.index[-1], "fin", capital)
            capital += posicion_abierta.pnl
            trades.append(posicion_abierta)
            equity[-1] = capital

        equity_series = pd.Series(equity[1:], index=df.index, name="equity")

        resultado = ResultadoBacktest(
            trades=trades,
            equity_curve=equity_series,
            capital_inicial=self.capital_inicial,
            señales=self.df["señal"],                 # ← NUEVO
            precios=self.df[["open", "high", "low", "close"]],  # ← NUEVO
        )
        resultado.metricas = calcular_metricas(resultado, self.capital_inicial)
        return resultado

    # ------------------------------------------------------------------
    def _cerrar_trade(
        self,
        trade: Trade,
        precio_salida: float,
        fecha_salida: pd.Timestamp,
        motivo: str,
        capital_actual: float,
    ) -> None:
        """Calcula PnL y comisiones y actualiza el trade."""
        # Slippage en la salida
        precio_salida_ajust = precio_salida
        if trade.direccion == "long":
            precio_salida_ajust *= (1 - self.slippage_pct)
        else:
            precio_salida_ajust *= (1 + self.slippage_pct)

        # PnL bruto
        if trade.direccion == "long":
            pnl_bruto = (precio_salida_ajust - trade.entrada_precio) * trade.qty
        else:
            pnl_bruto = (trade.entrada_precio - precio_salida_ajust) * trade.qty

        # Comisiones (entrada + salida)
        valor_entrada = trade.entrada_precio * trade.qty
        valor_salida = precio_salida_ajust * trade.qty
        comision = (valor_entrada + valor_salida) * self.comision_pct

        trade.salida_fecha = fecha_salida
        trade.salida_precio = precio_salida_ajust
        trade.motivo_salida = motivo
        trade.comision = comision
        trade.pnl = pnl_bruto - comision
        trade.pnl_pct = (trade.pnl / valor_entrada * 100) if valor_entrada else 0
        trade.duracion_velas = self._contar_velas(trade.entrada_fecha, fecha_salida)

    # ------------------------------------------------------------------
    def _pnl_no_realizado(self, trade: Trade, precio_actual: float) -> float:
        """PnL flotante de una posición abierta."""
        if trade.direccion == "long":
            return (precio_actual - trade.entrada_precio) * trade.qty
        return (trade.entrada_precio - precio_actual) * trade.qty

    # ------------------------------------------------------------------
    def _contar_velas(self, inicio: pd.Timestamp, fin: pd.Timestamp) -> int:
        """Nº de velas entre dos timestamps."""
        try:
            return int(self.df.index.get_loc(fin) - self.df.index.get_loc(inicio))
        except KeyError:
            return 0


# ============================================================================
# Métricas
# ============================================================================
def calcular_metricas(resultado: ResultadoBacktest, capital_inicial: float) -> dict:
    """Calcula las métricas clásicas del backtest."""
    trades = resultado.trades
    equity = resultado.equity_curve

    if not trades:
        return {
            "num_trades": 0,
            "retorno_total_pct": 0.0,
            "capital_final": capital_inicial,
        }

    # Retornos
    capital_final = capital_inicial + sum(t.pnl for t in trades)
    retorno_total_pct = (capital_final / capital_inicial - 1) * 100

    # Duración
    dias = (equity.index[-1] - equity.index[0]).days or 1
    años = dias / 365.25
    cagr = ((capital_final / capital_inicial) ** (1 / años) - 1) * 100 if años > 0 else 0

    # Retornos diarios/por vela
    retornos = equity.pct_change().dropna()

    # Sharpe (asumiendo 0% risk-free)
    if retornos.std() > 0:
        # Anualizar por nº de velas al año (cripto 24/7)
        velas_por_año = len(equity) / años if años > 0 else 365
        sharpe = (retornos.mean() / retornos.std()) * np.sqrt(velas_por_año)
    else:
        sharpe = 0.0

    # Sortino (solo downside)
    downside = retornos[retornos < 0]
    if len(downside) > 0 and downside.std() > 0:
        velas_por_año = len(equity) / años if años > 0 else 365
        sortino = (retornos.mean() / downside.std()) * np.sqrt(velas_por_año)
    else:
        sortino = 0.0

    # Max Drawdown
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd_pct = drawdown.min() * 100

    # Trades
    ganadores = [t for t in trades if t.pnl > 0]
    perdedores = [t for t in trades if t.pnl <= 0]
    winrate = len(ganadores) / len(trades) * 100 if trades else 0

    avg_win = np.mean([t.pnl for t in ganadores]) if ganadores else 0
    avg_loss = np.mean([t.pnl for t in perdedores]) if perdedores else 0

    total_win = sum(t.pnl for t in ganadores)
    total_loss = abs(sum(t.pnl for t in perdedores))
    profit_factor = total_win / total_loss if total_loss > 0 else float("inf")

    expectancy = np.mean([t.pnl for t in trades])

    # Duración media
    duracion_media = np.mean([t.duracion_velas for t in trades])

    return {
        "num_trades":          len(trades),
        "num_ganadores":       len(ganadores),
        "num_perdedores":      len(perdedores),
        "winrate_pct":         round(winrate, 2),
        "retorno_total_pct":   round(retorno_total_pct, 2),
        "cagr_pct":            round(cagr, 2),
        "capital_final":       round(capital_final, 2),
        "sharpe":              round(sharpe, 3),
        "sortino":             round(sortino, 3),
        "max_drawdown_pct":    round(max_dd_pct, 2),
        "avg_win":             round(avg_win, 2),
        "avg_loss":            round(avg_loss, 2),
        "profit_factor":       round(profit_factor, 3) if profit_factor != float("inf") else "∞",
        "expectancy":          round(expectancy, 2),
        "duracion_media_velas": round(duracion_media, 1),
    }


# ============================================================================
# CLI rápida de prueba
# ============================================================================
if __name__ == "__main__":
    from pathlib import Path
    from rich.console import Console
    from rich.table   import Table
    from src.data_loader import DataLoader
    from src.estrategias import listar_estrategias, obtener_estrategia

    console = Console()

    # Buscar un parquet con datos suficientes
    raiz = Path(__file__).resolve().parents[2]
    parquets = sorted((raiz / "data" / "raw").glob("*.parquet"))
    if not parquets:
        console.print("[red]No hay parquets. Ejecuta scripts/descargar_datos.py primero.[/red]")
        raise SystemExit(1)

    # Elegir el más largo (heurística: por tamaño)
    archivo = max(parquets, key=lambda p: p.stat().st_size)
    console.print(f"[blue]→[/blue] Usando {archivo.name}")
    df = pd.read_parquet(archivo)
    console.print(f"[blue]→[/blue] {len(df)} velas\n")

    # Probar todas las estrategias
    tabla = Table(title="Backtest por estrategia")
    tabla.add_column("Estrategia",  style="cyan")
    tabla.add_column("Trades",       justify="right")
    tabla.add_column("Winrate %",    justify="right", style="green")
    tabla.add_column("Retorno %",    justify="right", style="green")
    tabla.add_column("Max DD %",     justify="right", style="red")
    tabla.add_column("Sharpe",       justify="right", style="magenta")
    tabla.add_column("PF",           justify="right", style="yellow")

    for nombre in listar_estrategias():
        try:
            est = obtener_estrategia(nombre)
            bt = Backtest(
                df=df,
                estrategia=est,
                capital_inicial=10_000,
                comision_pct=0.1,
                slippage_pct=0.05,
                riesgo={
                    "modo": "porcentaje",
                    "sl_pct": 2.0, "tp_pct": 4.0,
                    "riesgo_pct": 2.0,
                },
                permitir_longs=True,
                permitir_shorts=True,
            )
            res = bt.ejecutar()
            m = res.metricas
            tabla.add_row(
                nombre,
                str(m.get("num_trades", 0)),
                f"{m.get('winrate_pct', 0):.1f}",
                f"{m.get('retorno_total_pct', 0):.1f}",
                f"{m.get('max_drawdown_pct', 0):.1f}",
                f"{m.get('sharpe', 0):.2f}",
                str(m.get("profit_factor", "—")),
            )
        except Exception as e:
            console.print(f"[red]✗ {nombre}: {e}[/red]")

    console.print(tabla)