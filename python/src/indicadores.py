"""
indicadores.py
==============
Cálculo de indicadores técnicos sobre DataFrames OHLCV.

Todos los indicadores:
- Reciben un pd.DataFrame con columnas: open, high, low, close, volume
- Devuelven una pd.Series o el DataFrame con columnas nuevas
- Usan pandas-ta cuando está disponible, con fallback manual

Uso:
----
    from src.indicadores import agregar_indicadores, sma, rsi, macd

    df = agregar_indicadores(df, ["sma_20", "sma_50", "rsi_14"])
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Intentar pandas-ta; si falla, usar implementación manual
# ---------------------------------------------------------------------------
try:
    import pandas_ta as pta
    _PANDAS_TA_DISPONIBLE = True
except ImportError:
    try:
        import pandas_ta_classic as pta  # fork moderno
        _PANDAS_TA_DISPONIBLE = True
    except ImportError:
        pta = None
        _PANDAS_TA_DISPONIBLE = False


# ============================================================================
# Medias móviles
# ============================================================================
def sma(serie: pd.Series, longitud: int = 20) -> pd.Series:
    """Media móvil simple."""
    return serie.rolling(window=longitud, min_periods=longitud).mean()


def ema(serie: pd.Series, longitud: int = 20) -> pd.Series:
    """Media móvil exponencial."""
    return serie.ewm(span=longitud, adjust=False, min_periods=longitud).mean()


def wma(serie: pd.Series, longitud: int = 20) -> pd.Series:
    """Media móvil ponderada."""
    pesos = np.arange(1, longitud + 1)
    return serie.rolling(window=longitud).apply(
        lambda x: np.dot(x, pesos) / pesos.sum(), raw=True
    )


# ============================================================================
# Osciladores
# ============================================================================
def rsi(serie: pd.Series, longitud: int = 14) -> pd.Series:
    """
    Índice de Fuerza Relativa (RSI).
    Implementación Wilder suavizada con manejo de división por cero.

    Casos límite:
    - Solo ganancias (media_perdida == 0): RSI = 100
    - Solo pérdidas  (media_ganancia == 0): RSI = 0
    - Sin movimiento (ambas == 0): RSI = 50
    """
    delta = serie.diff()
    ganancia = delta.clip(lower=0)
    perdida = -delta.clip(upper=0)

    media_ganancia = ganancia.ewm(alpha=1 / longitud, adjust=False, min_periods=longitud).mean()
    media_perdida = perdida.ewm(alpha=1 / longitud, adjust=False, min_periods=longitud).mean()

    # Calcular RS evitando división por cero
    rs = media_ganancia / media_perdida

    # Donde media_perdida == 0 y media_ganancia > 0 → RSI = 100
    # Donde media_ganancia == 0 y media_perdida > 0 → RSI = 0
    # Donde ambas == 0 → RSI = 50
    rsi_val = 100 - (100 / (1 + rs))

    # Aplicar correcciones en los casos límite
    rsi_val = rsi_val.where(media_perdida != 0, 100.0)         # todo ganancias
    rsi_val = rsi_val.where(media_ganancia != 0, 0.0)          # todo pérdidas
    rsi_val = rsi_val.where((media_ganancia != 0) | (media_perdida != 0), 50.0)  # sin movimiento

    return rsi_val


def estocastico(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k: int = 14, d: int = 3, suavizar: int = 3
) -> pd.DataFrame:
    """Oscilador estocástico %K y %D."""
    minimo = low.rolling(k).min()
    maximo = high.rolling(k).max()
    rango = (maximo - minimo).replace(0, np.nan)
    k_raw = 100 * (close - minimo) / rango
    k_suav = k_raw.rolling(suavizar).mean()
    d_suav = k_suav.rolling(d).mean()
    return pd.DataFrame({"stoch_k": k_suav, "stoch_d": d_suav})


# ============================================================================
# MACD
# ============================================================================
def macd(
    serie: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD: línea, señal e histograma."""
    ema_fast = ema(serie, fast)
    ema_slow = ema(serie, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histograma = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histograma,
    })


# ============================================================================
# Bollinger Bands
# ============================================================================
def bollinger(
    serie: pd.Series, longitud: int = 20, desviaciones: float = 2.0
) -> pd.DataFrame:
    """Bandas de Bollinger: superior, media, inferior."""
    base = sma(serie, longitud)
    dev = serie.rolling(longitud).std(ddof=0)
    return pd.DataFrame({
        "bb_upper": base + desviaciones * dev,
        "bb_middle": base,
        "bb_lower": base - desviaciones * dev,
    })


# ============================================================================
# Volatilidad
# ============================================================================
def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, longitud: int = 14
) -> pd.Series:
    """Average True Range (Wilder)."""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / longitud, adjust=False, min_periods=longitud).mean()


def volatilidad_historica(close: pd.Series, longitud: int = 20, anualizar: bool = True) -> pd.Series:
    """Volatilidad histórica (desv. est. de retornos log)."""
    retornos = np.log(close / close.shift())
    vol = retornos.rolling(longitud).std()
    if anualizar:
        # 365 días × 24h para cripto (mercado 24/7)
        vol = vol * np.sqrt(365 * 24)
    return vol


# ============================================================================
# Volumen
# ============================================================================
def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direccion = np.sign(close.diff()).fillna(0)
    return (direccion * volume).cumsum()


def volumen_medio(volume: pd.Series, longitud: int = 20) -> pd.Series:
    """Volumen medio móvil."""
    return volume.rolling(longitud).mean()


# ============================================================================
# API de alto nivel
# ============================================================================
_INDICADORES_DISPONIBLES = {
    "sma", "ema", "wma", "rsi", "estocastico", "macd",
    "bollinger", "atr", "volatilidad", "obv", "volumen_medio",
}


def agregar_indicadores(
    df: pd.DataFrame,
    indicadores: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Añade indicadores al DataFrame OHLCV.

    Parámetros
    ----------
    df : pd.DataFrame
        OHLCV con índice datetime y columnas open/high/low/close/volume.
    indicadores : lista de str, opcional
        Nombres tipo "sma_20", "ema_50", "rsi_14", "macd_12_26_9",
        "bb_20_2.0", "atr_14", etc.
        Si es None, aplica un set por defecto.

    Devuelve
    --------
    pd.DataFrame con columnas nuevas.
    """
    if indicadores is None:
        indicadores = [
            "sma_20", "sma_50", "ema_20", "ema_50",
            "rsi_14", "macd_12_26_9", "bb_20_2.0", "atr_14",
        ]

    df = df.copy()

    for spec in indicadores:
        partes = spec.split("_")
        nombre = partes[0]
        params = partes[1:]

        try:
            if nombre == "sma":
                p = int(params[0]) if params else 20
                df[f"sma_{p}"] = sma(df["close"], p)

            elif nombre == "ema":
                p = int(params[0]) if params else 20
                df[f"ema_{p}"] = ema(df["close"], p)

            elif nombre == "wma":
                p = int(params[0]) if params else 20
                df[f"wma_{p}"] = wma(df["close"], p)

            elif nombre == "rsi":
                p = int(params[0]) if params else 14
                df[f"rsi_{p}"] = rsi(df["close"], p)

            elif nombre == "macd":
                fast = int(params[0]) if len(params) > 0 else 12
                slow = int(params[1]) if len(params) > 1 else 26
                sig  = int(params[2]) if len(params) > 2 else 9
                sub = macd(df["close"], fast, slow, sig)
                for col in sub.columns:
                    df[f"{col}_{fast}_{slow}_{sig}"] = sub[col].values

            elif nombre == "bb":
                p = int(params[0]) if params else 20
                d = float(params[1]) if len(params) > 1 else 2.0
                sub = bollinger(df["close"], p, d)
                sufijo = f"{p}_{d}"
                for col in sub.columns:
                    df[f"{col}_{sufijo}"] = sub[col].values

            elif nombre == "atr":
                p = int(params[0]) if params else 14
                df[f"atr_{p}"] = atr(df["high"], df["low"], df["close"], p)

            elif nombre == "volatilidad":
                p = int(params[0]) if params else 20
                df[f"volatilidad_{p}"] = volatilidad_historica(df["close"], p)

            elif nombre == "obv":
                df["obv"] = obv(df["close"], df["volume"])

            elif nombre == "volumen_medio":
                p = int(params[0]) if params else 20
                df[f"volumen_medio_{p}"] = volumen_medio(df["volume"], p)

            elif nombre == "estocastico":
                k = int(params[0]) if len(params) > 0 else 14
                d = int(params[1]) if len(params) > 1 else 3
                sub = estocastico(df["high"], df["low"], df["close"], k, d)
                for col in sub.columns:
                    df[f"{col}_{k}_{d}"] = sub[col].values

            else:
                print(f"⚠ Indicador desconocido: {spec}")

        except Exception as e:
            print(f"✗ Error aplicando {spec}: {e}")

    return df


def listar_indicadores() -> list[str]:
    """Devuelve la lista de indicadores soportados."""
    return sorted(_INDICADORES_DISPONIBLES)


# ============================================================================
# CLI rápida de prueba
# ============================================================================
if __name__ == "__main__":
    from pathlib import Path
    from rich.console import Console
    from rich.table   import Table

    console = Console()

    # Buscar cualquier parquet en data/raw
    raiz = Path(__file__).resolve().parents[2]
    parquets = list((raiz / "data" / "raw").glob("*.parquet"))
    if not parquets:
        console.print("[red]No hay parquets en data/raw. Ejecuta scripts/descargar_datos.py primero.[/red]")
        raise SystemExit(1)

    archivo = parquets[0]
    console.print(f"[blue]→[/blue] Leyendo {archivo.name}")
    df = pd.read_parquet(archivo)

    df = agregar_indicadores(df)

    tabla = Table(title=f"Indicadores calculados sobre {archivo.name}")
    tabla.add_column("Indicador", style="cyan")
    tabla.add_column("Último valor", style="green")

    for col in df.columns:
        if col in ("open", "high", "low", "close", "volume"):
            continue
        ultimo = df[col].iloc[-1]
        tabla.add_row(col, f"{ultimo:.4f}" if pd.notna(ultimo) else "NaN")

    console.print(tabla)