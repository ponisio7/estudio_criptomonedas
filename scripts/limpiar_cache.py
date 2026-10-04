#!/usr/bin/env python3
"""
scripts/limpiar_cache.py
========================
Limpia la caché de datos parquet en data/raw/.

Uso:
----
    # Ver qué se borraría (dry-run)
    python scripts/limpiar_cache.py --dry-run

    # Borrar archivos con más de 30 días
    python scripts/limpiar_cache.py --dias 30

    # Borrar todo
    python scripts/limpiar_cache.py --todo

    # Borrar solo los de un exchange
    python scripts/limpiar_cache.py --exchange binance
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RAW = RAIZ / "data" / "raw"
RUTA_RESULTADOS = RAIZ / "data" / "resultados"

from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

console = Console()


def formato_tamaño(bytes_: int) -> str:
    """Convierte bytes a formato legible."""
    for unidad in ["B", "KB", "MB", "GB"]:
        if bytes_ < 1024:
            return f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def listar_archivos(carpeta: Path, exchange: str | None = None) -> list[Path]:
    """Lista parquets en la carpeta, filtrando por exchange si se indica."""
    if not carpeta.exists():
        return []
    archivos = list(carpeta.glob("*.parquet"))
    if exchange:
        archivos = [a for a in archivos if a.name.startswith(f"{exchange}_")]
    return sorted(archivos)


def archivos_antiguos(archivos: list[Path], dias: int) -> list[Path]:
    """Filtra archivos con más de N días de antigüedad (por fecha de modificación)."""
    limite = datetime.now() - timedelta(days=dias)
    return [
        a for a in archivos
        if datetime.fromtimestamp(a.stat().st_mtime) < limite
    ]


def borrar_archivos(archivos: list[Path], dry_run: bool = False) -> tuple[int, int]:
    """Borra archivos. Devuelve (n_borrados, bytes_liberados)."""
    n = 0
    bytes_ = 0
    for a in archivos:
        try:
            tamaño = a.stat().st_size
            if not dry_run:
                a.unlink()
            n += 1
            bytes_ += tamaño
        except Exception as e:
            console.print(f"[red]✗ Error borrando {a.name}: {e}[/red]")
    return n, bytes_


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpieza de caché de datos")
    parser.add_argument("--dias", type=int, default=30,
                        help="Borrar archivos con más de N días (default 30)")
    parser.add_argument("--todo", action="store_true",
                        help="Borrar TODOS los parquets en data/raw")
    parser.add_argument("--exchange", type=str, default=None,
                        help="Filtrar por exchange (ej. binance)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo mostrar qué se borraría")
    parser.add_argument("--incluir-resultados", action="store_true",
                        help="También limpiar data/resultados/")
    args = parser.parse_args()

    console.rule("[bold cyan]Limpieza de caché[/bold cyan]")

    # --- data/raw/ ---
    archivos = listar_archivos(RUTA_RAW, exchange=args.exchange)

    if not archivos:
        console.print("[yellow]No hay archivos que limpiar en data/raw/[/yellow]")
    else:
        if args.todo:
            a_borrar = archivos
            motivo = "TODOS"
        else:
            a_borrar = archivos_antiguos(archivos, args.dias)
            motivo = f"más de {args.dias} días"

        if not a_borrar:
            console.print(f"[green]✓[/green] No hay archivos con {motivo}")
        else:
            tabla = Table(title=f"Archivos a borrar ({motivo})")
            tabla.add_column("Archivo", style="cyan")
            tabla.add_column("Tamaño", justify="right", style="yellow")
            tabla.add_column("Modificado", style="dim")

            total_bytes = 0
            for a in a_borrar:
                stat = a.stat()
                tabla.add_row(
                    a.name,
                    formato_tamaño(stat.st_size),
                    datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                )
                total_bytes += stat.st_size

            console.print(tabla)
            console.print(
                f"\n[bold]Total:[/bold] {len(a_borrar)} archivos, "
                f"[yellow]{formato_tamaño(total_bytes)}[/yellow]"
            )

            if args.dry_run:
                console.print("[dim](dry-run: no se borró nada)[/dim]")
            else:
                if Confirm.ask("¿Borrar estos archivos?", default=False):
                    n, bytes_ = borrar_archivos(a_borrar, dry_run=False)
                    console.print(
                        f"[green]✓[/green] {n} archivos borrados, "
                        f"[yellow]{formato_tamaño(bytes_)}[/yellow] liberados"
                    )
                else:
                    console.print("[yellow]Cancelado[/yellow]")

    # --- data/resultados/ ---
    if args.incluir_resultados:
        console.rule("[bold cyan]Reportes en data/resultados/[/bold cyan]")
        reportes = sorted(RUTA_RESULTADOS.glob("reporte_*.html"))
        if not reportes:
            console.print("[yellow]No hay reportes[/yellow]")
        else:
            a_borrar = archivos_antiguos(reportes, args.dias) if not args.todo else reportes
            if not a_borrar:
                console.print(f"[green]✓[/green] No hay reportes con más de {args.dias} días")
            else:
                total = sum(a.stat().st_size for a in a_borrar)
                console.print(
                    f"[bold]{len(a_borrar)} reportes[/bold], "
                    f"[yellow]{formato_tamaño(total)}[/yellow]"
                )
                if args.dry_run:
                    console.print("[dim](dry-run)[/dim]")
                elif Confirm.ask("¿Borrar?", default=False):
                    n, bytes_ = borrar_archivos(a_borrar, dry_run=False)
                    console.print(f"[green]✓[/green] {n} reportes borrados")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())