#!/usr/bin/env python3
"""
scripts/descargar_datos.py
==========================
Descarga OHLCV de múltiples criptos a data/raw/.

Uso:
----
    python scripts/descargar_datos.py --simbolos BTC/USDT ETH/USDT SOL/USDT \
        --timeframe 4h --desde 2022-01-01 --hasta 2024-12-31
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Añadir python/ al path para importar src
RUTA_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUTA_RAIZ / "python"))

from src.data_loader import DataLoader  # noqa: E402
from rich.console import Console         # noqa: E402

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(description="Descargar OHLCV multi-cripto")
    parser.add_argument("--exchange",  default="binance")
    parser.add_argument("--simbolos",  nargs="+", default=["BTC/USDT"])
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--desde",     default="2022-01-01")
    parser.add_argument("--hasta",     default="2024-12-31")
    parser.add_argument("--forzar",    action="store_true",
                        help="Ignorar caché y descargar de nuevo")
    args = parser.parse_args()

    dl = DataLoader(exchange=args.exchange)
    errores = 0

    for simbolo in args.simbolos:
        console.rule(f"[bold cyan]{simbolo}[/bold cyan]")
        try:
            df = dl.cargar(
                simbolo=simbolo,
                timeframe=args.timeframe,
                desde=args.desde,
                hasta=args.hasta,
                forzar_descarga=args.forzar,
            )
            console.print(
                f"[green]✓[/green] {simbolo}: {len(df):,} velas "
                f"({df.index[0].date()} → {df.index[-1].date()})\n"
            )
        except Exception as e:
            console.print(f"[red]✗ Error en {simbolo}:[/red] {e}\n")
            errores += 1

    if errores:
        console.print(f"[yellow]Terminado con {errores} error(es)[/yellow]")
        return 1
    console.print("[bold green]✓ Descarga completada[/bold green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())