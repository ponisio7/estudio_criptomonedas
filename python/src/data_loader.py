"""
data_loader.py
==============
Carga de datos OHLCV de cualquier criptomoneda desde cualquier exchange
soportado por ccxt, con caché local en formato parquet.

Uso rápido:
------------
    from src.data_loader import DataLoader
    dl = DataLoader(exchange="binance")
    df = dl.cargar(simbolo="BTC/USDT", timeframe="4h",
                   desde="2022-01-01", hasta="2024-12-31")
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import ccxt
import pandas as pd
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tqdm import tqdm

console = Console()

# ============================================================================
# Configuración por defecto
# ============================================================================
RUTA_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_CONFIG   = RUTA_PROYECTO / "python" / "config.yaml"
RUTA_CACHE    = RUTA_PROYECTO / "data" / "raw"


def cargar_config(ruta: Optional[Path] = None) -> dict:
    """Carga config.yaml y devuelve un dict."""
    ruta = ruta or RUTA_CONFIG
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# Clase principal
# ============================================================================
class DataLoader:
    """
    Descarga OHLCV de cualquier exchange vía ccxt con caché parquet.
    """

    def __init__(
        self,
        exchange: str = "binance",
        cache_dir: Optional[Path] = None,
        rate_limit: bool = True,
    ):
        self.exchange_name = exchange
        self.cache_dir     = Path(cache_dir) if cache_dir else RUTA_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Inicializar exchange ccxt
        if not hasattr(ccxt, exchange):
            raise ValueError(f"Exchange '{exchange}' no soportado por ccxt")

        self.exchange = getattr(ccxt, exchange)({
            "enableRateLimit": rate_limit,
            "options": {"defaultType": "spot"},
        })

        console.print(f"[green]✓[/green] Exchange: [cyan]{exchange}[/cyan]")

    # ------------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------------
    def _ruta_cache(
        self, simbolo: str, timeframe: str, desde: str, hasta: str
    ) -> Path:
        """Construye el nombre del archivo de caché."""
        simbolo_limpio = simbolo.replace("/", "_")
        nombre = f"{self.exchange_name}_{simbolo_limpio}_{timeframe}_{desde}_{hasta}.parquet"
        return self.cache_dir / nombre

    @staticmethod
    def _a_timestamp(fecha: str) -> int:
        """Convierte 'YYYY-MM-DD' a milisegundos UTC."""
        dt = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    # ------------------------------------------------------------------------
    # Descarga paginada
    # ------------------------------------------------------------------------
    def _descargar_paginado(
        self,
        simbolo: str,
        timeframe: str,
        desde_ms: int,
        hasta_ms: int,
    ) -> pd.DataFrame:
        """
        Descarga OHLCV en bloques de 1000 velas hasta cubrir el rango.
        """
        todas: list[list] = []
        cursor = desde_ms
        limite = 1000

        # Estimación de iteraciones para la barra de progreso
        tf_ms = self.exchange.parse_timeframe(timeframe) * 1000
        total_estimado = max(1, (hasta_ms - desde_ms) // (tf_ms * limite) + 1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            tarea = progress.add_task(
                f"Descargando {simbolo} {timeframe}...", total=total_estimado
            )

            while cursor < hasta_ms:
                try:
                    velas = self.exchange.fetch_ohlcv(
                        symbol=simbolo,
                        timeframe=timeframe,
                        since=cursor,
                        limit=limite,
                    )
                except ccxt.NetworkError as e:
                    console.print(f"[yellow]⚠ Error de red:[/yellow] {e}. Reintentando en 3s...")
                    time.sleep(3)
                    continue
                except ccxt.ExchangeError as e:
                    console.print(f"[red]✗ Error del exchange:[/red] {e}")
                    break

                if not velas:
                    break

                todas.extend(velas)
                ultimo_ts = velas[-1][0]

                # Cortar si ya pasamos el rango
                if ultimo_ts >= hasta_ms:
                    break

                # Avanzar cursor
                cursor = ultimo_ts + tf_ms

                # Evitar bucle infinito si el exchange devuelve lo mismo
                if len(velas) < limite:
                    break

                progress.update(tarea, advance=1)

        if not todas:
            raise ValueError(f"Sin datos para {simbolo} {timeframe}")

        # Construir DataFrame
        df = pd.DataFrame(
            todas, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
        df = df[df["timestamp"] <= pd.to_datetime(hasta_ms, unit="ms", utc=True)]
        df = df.set_index("timestamp")
        return df

    # ------------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------------
    def cargar(
        self,
        simbolo: str,
        timeframe: str = "4h",
        desde: str = "2022-01-01",
        hasta: str = "2024-12-31",
        usar_cache: bool = True,
        forzar_descarga: bool = False,
    ) -> pd.DataFrame:
        """
        Carga OHLCV de un símbolo. Usa caché parquet si existe.

        Parámetros
        ----------
        simbolo : str
            Par en formato ccxt, ej. "BTC/USDT".
        timeframe : str
            "1m", "5m", "15m", "1h", "4h", "1d", "1w".
        desde, hasta : str
            Fechas "YYYY-MM-DD".
        usar_cache : bool
            Si True, lee de data/raw si existe.
        forzar_descarga : bool
            Si True, ignora caché y descarga de nuevo.

        Devuelve
        --------
        pd.DataFrame con índice datetime UTC y columnas OHLCV.
        """
        ruta = self._ruta_cache(simbolo, timeframe, desde, hasta)

        # 1) Caché
        if usar_cache and not forzar_descarga and ruta.exists():
            console.print(f"[blue]→[/blue] Leyendo caché: [dim]{ruta.name}[/dim]")
            return pd.read_parquet(ruta)

        # 2) Descarga
        desde_ms = self._a_timestamp(desde)
        hasta_ms = self._a_timestamp(hasta)

        console.print(
            f"[blue]↓[/blue] Descargando [cyan]{simbolo}[/cyan] "
            f"[magenta]{timeframe}[/magenta] desde {desde} hasta {hasta}"
        )

        df = self._descargar_paginado(simbolo, timeframe, desde_ms, hasta_ms)

        # 3) Guardar caché
        df.to_parquet(ruta)
        console.print(
            f"[green]✓[/green] {len(df):,} velas guardadas en [dim]{ruta.name}[/dim]"
        )
        return df


# ============================================================================
# CLI rápida
# ============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Descargar OHLCV de una cripto")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--simbolo",  default="BTC/USDT")
    parser.add_argument("--timeframe",default="4h")
    parser.add_argument("--desde",    default="2022-01-01")
    parser.add_argument("--hasta",    default="2024-12-31")
    parser.add_argument("--forzar",   action="store_true")
    args = parser.parse_args()

    dl = DataLoader(exchange=args.exchange)
    df = dl.cargar(
        simbolo=args.simbolo,
        timeframe=args.timeframe,
        desde=args.desde,
        hasta=args.hasta,
        forzar_descarga=args.forzar,
    )
    console.print(df.tail())
    console.print(f"\n[bold]Total velas:[/bold] {len(df):,}")
    console.print(f"[bold]Rango:[/bold] {df.index[0]} → {df.index[-1]}")