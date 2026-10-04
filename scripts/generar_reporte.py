#!/usr/bin/env python3
"""
scripts/generar_reporte.py
==========================
Genera un reporte HTML desde CLI.

Uso:
----
    python scripts/generar_reporte.py \
        --simbolo BTC/USDT \
        --timeframe 4h \
        --desde 2024-01-01 \
        --hasta 2024-12-31 \
        --estrategia cruce_sma \
        --params sma_rapida=20 sma_lenta=50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "python"))

from src.data_loader import DataLoader           # noqa: E402
from src.estrategias import obtener_estrategia   # noqa: E402
from src.backtest import Backtest                # noqa: E402
from src.reportes import generar_reporte         # noqa: E402
from rich.console import Console                 # noqa: E402

console = Console()


def parsear_params(lista: list[str]) -> dict:
    """Convierte ['sma_rapida=20', 'sma_lenta=50'] en {'sma_rapida': 20, 'sma_lenta': 50}."""
    params = {}
    for item in lista:
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        try:
            params[k] = int(v)
        except ValueError:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="Generar reporte HTML de backtest")
    parser.add_argument("--exchange",  default="binance")
    parser.add_argument("--simbolo",   default="BTC/USDT")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--desde",     default="2024-01-01")
    parser.add_argument("--hasta",     default="2024-12-31")
    parser.add_argument("--estrategia", default="cruce_sma")
    parser.add_argument("--params",    nargs="*", default=[])
    parser.add_argument("--capital",   type=float, default=10000)
    parser.add_argument("--comision",  type=float, default=0.1)
    parser.add_argument("--slippage",  type=float, default=0.05)
    parser.add_argument("--modo-riesgo", default="porcentaje")
    parser.add_argument("--sl-pct",    type=float, default=2.0)
    parser.add_argument("--tp-pct",    type=float, default=4.0)
    parser.add_argument("--atr-mult-sl", type=float, default=1.5)
    parser.add_argument("--atr-mult-tp", type=float, default=3.0)
    parser.add_argument("--longs",  action="store_true", default=True)
    parser.add_argument("--shorts", action="store_true")
    parser.add_argument("--salida", type=str, default=None)
    args = parser.parse_args()

    params = parsear_params(args.params)

    console.rule(f"[bold cyan]Backtest {args.simbolo} {args.timeframe}[/bold cyan]")

    # Datos
    dl = DataLoader(exchange=args.exchange)
    df = dl.cargar(args.simbolo, args.timeframe, args.desde, args.hasta)

    # Estrategia
    est = obtener_estrategia(args.estrategia, **params)

    # Backtest
    bt = Backtest(
        df=df,
        estrategia=est,
        capital_inicial=args.capital,
        comision_pct=args.comision,
        slippage_pct=args.slippage,
        riesgo={
            "modo": args.modo_riesgo,
            "sl_pct": args.sl_pct, "tp_pct": args.tp_pct,
            "atr_mult_sl": args.atr_mult_sl, "atr_mult_tp": args.atr_mult_tp,
            "riesgo_pct": 2.0,
        },
        permitir_longs=args.longs,
        permitir_shorts=args.shorts,
    )
    resultado = bt.ejecutar()

    console.print(f"\n[bold]Resultados:[/bold]")
    for k, v in resultado.metricas.items():
        console.print(f"  {k:.<28} {v}")

    # Reporte
    config = {
        "exchange": args.exchange,
        "simbolo": args.simbolo,
        "timeframe": args.timeframe,
        "desde": args.desde,
        "hasta": args.hasta,
        "estrategia": args.estrategia,
        "params_estrategia": params,
        "riesgo": {
            "modo": args.modo_riesgo,
            "sl_pct": args.sl_pct, "tp_pct": args.tp_pct,
            "atr_mult_sl": args.atr_mult_sl, "atr_mult_tp": args.atr_mult_tp,
        },
        "costes": {
            "capital": args.capital,
            "comision": args.comision,
            "slippage": args.slippage,
        },
        "permitir_longs": args.longs,
        "permitir_shorts": args.shorts,
    }

    ruta = generar_reporte(resultado, config, df=df, ruta_salida=args.salida)
    console.print(f"\n[bold green]✓ Reporte generado:[/bold green] [cyan]{ruta}[/cyan]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())