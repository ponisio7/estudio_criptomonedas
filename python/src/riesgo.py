"""
riesgo.py
=========
Gestión de riesgo: Stop Loss, Take Profit y cálculo de tamaño de posición.

Modos de SL/TP:
    - "ninguno":    sin stops
    - "porcentaje": SL/TP en % respecto al precio de entrada
    - "atr":        SL/TP en múltiplos de ATR

Uso:
----
    from src.riesgo import calcular_sl_tp, calcular_qty

    sl, tp = calcular_sl_tp(
        precio_entrada=50000,
        direccion="long",
        atr=500,
        modo="atr",
        params={"atr_mult_sl": 1.5, "atr_mult_tp": 3.0},
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.indicadores import atr as atr_ind


Direccion = Literal["long", "short"]
ModoSLTP  = Literal["ninguno", "porcentaje", "atr"]


# ============================================================================
# Cálculo de SL/TP
# ============================================================================
def calcular_sl_tp(
    precio_entrada: float,
    direccion: Direccion,
    atr_actual: float | None = None,
    modo: ModoSLTP = "porcentaje",
    sl_pct: float = 2.0,
    tp_pct: float = 4.0,
    atr_mult_sl: float = 1.5,
    atr_mult_tp: float = 3.0,
) -> tuple[float | None, float | None]:
    """
    Calcula los niveles de Stop Loss y Take Profit.

    Parámetros
    ----------
    precio_entrada : float
    direccion : "long" | "short"
    atr_actual : float | None
        Valor del ATR en la vela de entrada (obligatorio si modo="atr").
    modo : "ninguno" | "porcentaje" | "atr"
    sl_pct, tp_pct : float
        Porcentajes de SL y TP (solo modo="porcentaje").
    atr_mult_sl, atr_mult_tp : float
        Múltiplos de ATR (solo modo="atr").

    Devuelve
    --------
    (stop_loss, take_profit). None si modo="ninguno" o falta ATR.
    """
    if modo == "ninguno":
        return None, None

    if direccion not in ("long", "short"):
        raise ValueError(f"dirección inválida: {direccion}")

    if modo == "porcentaje":
        if direccion == "long":
            sl = precio_entrada * (1 - sl_pct / 100)
            tp = precio_entrada * (1 + tp_pct / 100)
        else:
            sl = precio_entrada * (1 + sl_pct / 100)
            tp = precio_entrada * (1 - tp_pct / 100)
        return sl, tp

    if modo == "atr":
        if atr_actual is None or np.isnan(atr_actual) or atr_actual <= 0:
            return None, None
        if direccion == "long":
            sl = precio_entrada - atr_actual * atr_mult_sl
            tp = precio_entrada + atr_actual * atr_mult_tp
        else:
            sl = precio_entrada + atr_actual * atr_mult_sl
            tp = precio_entrada - atr_actual * atr_mult_tp
        return sl, tp

    raise ValueError(f"modo SL/TP desconocido: {modo}")


# ============================================================================
# Cálculo de tamaño de posición
# ============================================================================
def calcular_qty(
    capital: float,
    precio_entrada: float,
    stop_loss: float | None,
    riesgo_pct: float = 2.0,
    modo: Literal["riesgo_fijo", "porcentaje_capital"] = "riesgo_fijo",
) -> float:
    """
    Calcula la cantidad a comprar/vender.

    Parámetros
    ----------
    capital : float
        Capital disponible en el momento de la entrada.
    precio_entrada : float
    stop_loss : float | None
        Necesario para modo="riesgo_fijo".
    riesgo_pct : float
        % del capital a arriesgar por operación.
    modo : "riesgo_fijo" | "porcentaje_capital"
        - riesgo_fijo: arriesga `riesgo_pct`% del capital hasta el SL.
        - porcentaje_capital: usa `riesgo_pct`% del capital como tamaño de posición.

    Devuelve
    --------
    float: cantidad en unidades del activo.
    """
    if modo == "porcentaje_capital":
        return (capital * riesgo_pct / 100) / precio_entrada

    if modo == "riesgo_fijo":
        if stop_loss is None:
            # Sin SL → usa porcentaje de capital por defecto
            return (capital * riesgo_pct / 100) / precio_entrada
        distancia = abs(precio_entrada - stop_loss)
        if distancia <= 0:
            return (capital * riesgo_pct / 100) / precio_entrada
        riesgo_monetario = capital * riesgo_pct / 100
        return riesgo_monetario / distancia

    raise ValueError(f"modo qty desconocido: {modo}")


# ============================================================================
# Trailing stop
# ============================================================================
def actualizar_trailing_stop(
    precio_actual: float,
    sl_actual: float | None,
    direccion: Direccion,
    distancia: float,
) -> float:
    """
    Actualiza un trailing stop.

    Parámetros
    ----------
    precio_actual : float
    sl_actual : float | None
        Stop Loss previo (puede ser None en la primera llamada).
    direccion : "long" | "short"
    distancia : float
        Distancia al precio actual (ej. 1.5 × ATR).

    Devuelve
    --------
    Nuevo Stop Loss (nunca empeora).
    """
    if direccion == "long":
        candidato = precio_actual - distancia
        if sl_actual is None:
            return candidato
        return max(sl_actual, candidato)

    if direccion == "short":
        candidato = precio_actual + distancia
        if sl_actual is None:
            return candidato
        return min(sl_actual, candidato)

    raise ValueError(f"dirección inválida: {direccion}")


# ============================================================================
# Utilidad: aplicar ATR al DataFrame
# ============================================================================
def agregar_atr(df: pd.DataFrame, longitud: int = 14) -> pd.DataFrame:
    """Añade columna atr_{longitud} al DataFrame."""
    df = df.copy()
    df[f"atr_{longitud}"] = atr_ind(df["high"], df["low"], df["close"], longitud)
    return df


# ============================================================================
# CLI rápida de prueba
# ============================================================================
if __name__ == "__main__":
    from rich.console import Console
    from rich.table   import Table

    console = Console()

    console.rule("[bold]Ejemplos de SL/TP[/bold]")

    tabla = Table(title="Cálculo de SL/TP")
    tabla.add_column("Modo", style="cyan")
    tabla.add_column("Dirección", style="magenta")
    tabla.add_column("Entrada", justify="right")
    tabla.add_column("SL", style="red", justify="right")
    tabla.add_column("TP", style="green", justify="right")

    # Ejemplos
    casos = [
        ("porcentaje", "long",  50000, None, {}),
        ("porcentaje", "short", 50000, None, {}),
        ("atr",        "long",  50000, 500,  {}),
        ("atr",        "short", 50000, 500,  {}),
        ("ninguno",    "long",  50000, None, {}),
    ]

    for modo, direccion, entrada, atr_v, _ in casos:
        sl, tp = calcular_sl_tp(
            precio_entrada=entrada,
            direccion=direccion,
            atr_actual=atr_v,
            modo=modo,
        )
        tabla.add_row(
            modo, direccion, f"{entrada:,.0f}",
            f"{sl:,.2f}" if sl else "—",
            f"{tp:,.2f}" if tp else "—",
        )

    console.print(tabla)

    # Tamaño de posición
    console.rule("[bold]Tamaño de posición[/bold]")
    capital = 10_000
    entrada = 50_000
    sl, _ = calcular_sl_tp(entrada, "long", modo="porcentaje", sl_pct=2)
    qty = calcular_qty(capital, entrada, sl, riesgo_pct=2, modo="riesgo_fijo")
    riesgo_real = qty * abs(entrada - sl)
    console.print(f"Capital:          ${capital:,.0f}")
    console.print(f"Precio entrada:   ${entrada:,.0f}")
    console.print(f"Stop Loss:        ${sl:,.0f}")
    console.print(f"Riesgo por op:    2% = ${capital * 0.02:,.0f}")
    console.print(f"Cantidad (qty):   {qty:.6f} BTC")
    console.print(f"Valor posición:   ${qty * entrada:,.0f}")
    console.print(f"Riesgo real:      ${riesgo_real:,.0f}")