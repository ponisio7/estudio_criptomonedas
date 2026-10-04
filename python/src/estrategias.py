"""
estrategias.py
==============
Estrategias de trading en Python, equivalentes al Builder Pine.

Todas las estrategias heredan de la clase base `Estrategia` e implementan
el método `generar_senales(df) -> pd.Series` con valores:
    +1 = señal LONG
    -1 = señal SHORT
     0 = sin señal

Uso:
----
    from src.estrategias import obtener_estrategia

    est = obtener_estrategia("cruce_sma", sma_rapida=20, sma_lenta=50)
    senales = est.generar_senales(df)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import numpy as np
import pandas as pd

from src.indicadores import sma, ema, rsi, macd, bollinger, atr


# ============================================================================
# Clase base
# ============================================================================
class Estrategia(ABC):
    """Clase base de todas las estrategias."""

    nombre: str = "base"
    descripcion: str = ""

    def __init__(self, **kwargs):
        """Guarda los parámetros específicos en self.params."""
        self.params = kwargs

    @abstractmethod
    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        """
        Genera señales sobre el DataFrame OHLCV.

        Devuelve
        --------
        pd.Series con valores enteros:
            +1 → long
            -1 → short
             0 → nada
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.params}>"


# ============================================================================
# Utilidad: señales a partir de condiciones
# ============================================================================
def _combinar_senales(
    cond_long: pd.Series,
    cond_short: pd.Series,
) -> pd.Series:
    """Combina condiciones booleanas en una serie de señales +1/0/-1."""
    senales = pd.Series(0, index=cond_long.index, dtype=int)
    senales[cond_long.fillna(False)] = 1
    senales[cond_short.fillna(False)] = -1
    return senales


def _cruce_alcista(a: pd.Series, b: pd.Series) -> pd.Series:
    """True cuando a cruza al alza b."""
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cruce_bajista(a: pd.Series, b: pd.Series) -> pd.Series:
    """True cuando a cruza a la baja b."""
    return (a < b) & (a.shift(1) >= b.shift(1))


# ============================================================================
# 1. Cruce SMA
# ============================================================================
class EstrategiaCruceSMA(Estrategia):
    """Cruce de medias móviles simples."""

    nombre = "cruce_sma"
    descripcion = "SMA rápida cruza SMA lenta"

    def __init__(self, sma_rapida: int = 20, sma_lenta: int = 50, **kwargs):
        super().__init__(sma_rapida=sma_rapida, sma_lenta=sma_lenta, **kwargs)
        self.sma_rapida = sma_rapida
        self.sma_lenta = sma_lenta

    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        rapida = sma(df["close"], self.sma_rapida)
        lenta = sma(df["close"], self.sma_lenta)

        cond_long = _cruce_alcista(rapida, lenta)
        cond_short = _cruce_bajista(rapida, lenta)

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# 2. RSI + SMA
# ============================================================================
class EstrategiaRSISMA(Estrategia):
    """RSI sale de zona extrema + filtro de tendencia por SMA."""

    nombre = "rsi_sma"
    descripcion = "RSI sale de sobreventa/sobrecompra con filtro SMA"

    def __init__(
        self,
        rsi_len: int = 14,
        rsi_sobrev: float = 30,
        rsi_sobrec: float = 70,
        sma_tendencia: int = 200,
        **kwargs,
    ):
        super().__init__(
            rsi_len=rsi_len, rsi_sobrev=rsi_sobrev,
            rsi_sobrec=rsi_sobrec, sma_tendencia=sma_tendencia, **kwargs,
        )
        self.rsi_len = rsi_len
        self.rsi_sobrev = rsi_sobrev
        self.rsi_sobrec = rsi_sobrec
        self.sma_tendencia = sma_tendencia

    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        rsi_val = rsi(df["close"], self.rsi_len)
        sma_tend = sma(df["close"], self.sma_tendencia)

        # Long: precio > SMA tendencia Y RSI sale de sobreventa
        cond_long = (
            (df["close"] > sma_tend)
            & _cruce_alcista(rsi_val, pd.Series(self.rsi_sobrev, index=rsi_val.index))
        )

        # Short: precio < SMA tendencia Y RSI sale de sobrecompra
        cond_short = (
            (df["close"] < sma_tend)
            & _cruce_bajista(rsi_val, pd.Series(self.rsi_sobrec, index=rsi_val.index))
        )

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# 3. MACD
# ============================================================================
class EstrategiaMACD(Estrategia):
    """Cruce de línea MACD con señal."""

    nombre = "macd"
    descripcion = "MACD cruza su línea de señal"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, **kwargs):
        super().__init__(fast=fast, slow=slow, signal=signal, **kwargs)
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        sub = macd(df["close"], self.fast, self.slow, self.signal)
        linea = sub["macd"]
        señal = sub["macd_signal"]

        cond_long = _cruce_alcista(linea, señal)
        cond_short = _cruce_bajista(linea, señal)

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# 4. Bollinger Bands
# ============================================================================
class EstrategiaBollinger(Estrategia):
    """Reversión a la media en extremos de Bollinger."""

    nombre = "bollinger"
    descripcion = "Precio toca banda inferior/superior"

    def __init__(self, longitud: int = 20, desviaciones: float = 2.0, **kwargs):
        super().__init__(longitud=longitud, desviaciones=desviaciones, **kwargs)
        self.longitud = longitud
        self.desviaciones = desviaciones

    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        sub = bollinger(df["close"], self.longitud, self.desviaciones)
        sup = sub["bb_upper"]
        inf = sub["bb_lower"]

        # Long: precio cruza al alza la banda inferior (rebote)
        cond_long = _cruce_alcista(df["close"], inf)
        # Short: precio cruza a la baja la banda superior
        cond_short = _cruce_bajista(df["close"], sup)

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# 5. EMA Tendencia
# ============================================================================
class EstrategiaEMATendencia(Estrategia):
    """Cruce de EMAs (más reactivo que SMA)."""

    nombre = "ema_tendencia"
    descripcion = "EMA rápida cruza EMA lenta"

    def __init__(self, ema_rapida: int = 20, ema_lenta: int = 50, **kwargs):
        super().__init__(ema_rapida=ema_rapida, ema_lenta=ema_lenta, **kwargs)
        self.ema_rapida = ema_rapida
        self.ema_lenta = ema_lenta

    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        rapida = ema(df["close"], self.ema_rapida)
        lenta = ema(df["close"], self.ema_lenta)

        cond_long = _cruce_alcista(rapida, lenta)
        cond_short = _cruce_bajista(rapida, lenta)

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# 6. Custom (parametrizable)
# ============================================================================
class EstrategiaCustom(Estrategia):
    """
    Estrategia configurable con dos condiciones combinadas con Y/O.

    Tipos de condición soportados:
        - "RSI < X"
        - "RSI > X"
        - "Precio > SMA"
        - "Precio < SMA"
        - "MACD cruza señal"
    """

    nombre = "custom"
    descripcion = "Dos condiciones configurables con operador lógico"

    def __init__(
        self,
        c1_tipo: str = "RSI < X",
        c1_valor: float = 30,
        operador: Literal["Y", "O"] = "Y",
        c2_tipo: str = "Precio > SMA",
        c2_valor: float = 200,
        **kwargs,
    ):
        super().__init__(
            c1_tipo=c1_tipo, c1_valor=c1_valor,
            operador=operador,
            c2_tipo=c2_tipo, c2_valor=c2_valor, **kwargs,
        )
        self.c1_tipo = c1_tipo
        self.c1_valor = c1_valor
        self.operador = operador
        self.c2_tipo = c2_tipo
        self.c2_valor = c2_valor

    # ------------------------------------------------------------------
    def _evaluar(self, df: pd.DataFrame, tipo: str, valor: float) -> pd.Series:
        """Devuelve una serie booleana según el tipo de condición."""
        if tipo == "RSI < X":
            r = rsi(df["close"], 14)
            return r < valor

        if tipo == "RSI > X":
            r = rsi(df["close"], 14)
            return r > valor

        if tipo == "Precio > SMA":
            s = sma(df["close"], int(valor))
            return df["close"] > s

        if tipo == "Precio < SMA":
            s = sma(df["close"], int(valor))
            return df["close"] < s

        if tipo == "MACD cruza señal":
            sub = macd(df["close"], 12, 26, 9)
            return _cruce_alcista(sub["macd"], sub["macd_signal"])

        raise ValueError(f"Tipo de condición desconocido: {tipo}")

    # ------------------------------------------------------------------
    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        c1 = self._evaluar(df, self.c1_tipo, self.c1_valor)
        c2 = self._evaluar(df, self.c2_tipo, self.c2_valor)

        if self.operador == "Y":
            señal = c1 & c2
        else:  # "O"
            señal = c1 | c2

        señal = señal.fillna(False)

        # Long por defecto; short cuando RSI > sobrecompra
        cond_long = señal
        cond_short = señal & (self.c1_tipo == "RSI > X")

        return _combinar_senales(cond_long, cond_short)


# ============================================================================
# Registro de estrategias
# ============================================================================
_REGISTRO = {
    "cruce_sma":     EstrategiaCruceSMA,
    "rsi_sma":       EstrategiaRSISMA,
    "macd":          EstrategiaMACD,
    "bollinger":     EstrategiaBollinger,
    "ema_tendencia": EstrategiaEMATendencia,
    "custom":        EstrategiaCustom,
}


def obtener_estrategia(nombre: str, **kwargs) -> Estrategia:
    """
    Factory de estrategias.

    Parámetros
    ----------
    nombre : str
        Uno de: cruce_sma, rsi_sma, macd, bollinger, ema_tendencia, custom.
    **kwargs
        Parámetros específicos de la estrategia.

    Devuelve
    --------
    Instancia de Estrategia lista para usar.
    """
    if nombre not in _REGISTRO:
        disponibles = ", ".join(_REGISTRO.keys())
        raise ValueError(f"Estrategia '{nombre}' no existe. Disponibles: {disponibles}")
    return _REGISTRO[nombre](**kwargs)


def listar_estrategias() -> list[str]:
    """Devuelve la lista de estrategias disponibles."""
    return sorted(_REGISTRO.keys())


# ============================================================================
# CLI rápida de prueba
# ============================================================================
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Añadir python/ al sys.path para que 'from src.xxx' funcione
    raiz_python = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(raiz_python))

    # Reimportar con el path ya corregido
    from src.estrategias import obtener_estrategia, listar_estrategias

    from rich.console import Console
    from rich.table import Table

    console = Console()

    raiz = raiz_python.parent
    parquets = list((raiz / "data" / "raw").glob("*.parquet"))
    if not parquets:
        console.print("[red]No hay parquets. Ejecuta scripts/descargar_datos.py primero.[/red]")
        raise SystemExit(1)

    archivo = parquets[0]
    console.print(f"[blue]→[/blue] Leyendo {archivo.name}")
    df = pd.read_parquet(archivo)

    tabla = Table(title=f"Señales por estrategia sobre {archivo.name}")
    tabla.add_column("Estrategia", style="cyan")
    tabla.add_column("Longs",  style="green", justify="right")
    tabla.add_column("Shorts", style="red",   justify="right")
    tabla.add_column("Total",  style="white", justify="right")

    for nombre in listar_estrategias():
        est = obtener_estrategia(nombre)
        señales = est.generar_senales(df)
        longs  = (señales == 1).sum()
        shorts = (señales == -1).sum()
        tabla.add_row(nombre, str(longs), str(shorts), str(longs + shorts))

    console.print(tabla)