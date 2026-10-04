"""
Tests unitarios para estrategias.py
Ejecutar: pytest python/tests/test_estrategias.py -v
"""

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.estrategias import (
    EstrategiaCruceSMA,
    EstrategiaRSISMA,
    EstrategiaMACD,
    EstrategiaBollinger,
    EstrategiaEMATendencia,
    EstrategiaCustom,
    obtener_estrategia,
    listar_estrategias,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def df_alcista():
    """DataFrame con tendencia alcista clara."""
    n = 200
    close = 100 + np.linspace(0, 50, n) + np.random.RandomState(42).randn(n) * 0.5
    high = close + 0.5
    low = close - 0.5
    open_ = close - 0.2
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": np.ones(n) * 100,
    }, index=idx)


@pytest.fixture
def df_bajista():
    """DataFrame con tendencia bajista clara."""
    n = 200
    close = 200 - np.linspace(0, 80, n) + np.random.RandomState(7).randn(n) * 0.5
    high = close + 0.5
    low = close - 0.5
    open_ = close + 0.2
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": np.ones(n) * 100,
    }, index=idx)


@pytest.fixture
def df_oscilante():
    """DataFrame que oscila (senoide) → muchas señales."""
    n = 300
    x = np.linspace(0, 8 * np.pi, n)
    close = 100 + 20 * np.sin(x) + np.random.RandomState(3).randn(n) * 0.3
    high = close + 0.5
    low = close - 0.5
    open_ = close
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": np.ones(n) * 100,
    }, index=idx)


# ---------------------------------------------------------------------------
# Tests generales
# ---------------------------------------------------------------------------
def test_listar_estrategias():
    lista = listar_estrategias()
    assert "cruce_sma" in lista
    assert "rsi_sma" in lista
    assert "macd" in lista
    assert "bollinger" in lista
    assert "ema_tendencia" in lista
    assert "custom" in lista


def test_obtener_estrategia_desconocida():
    with pytest.raises(ValueError, match="no existe"):
        obtener_estrategia("inexistente")


def test_senales_solo_tres_valores(df_oscilante):
    """Las señales solo pueden ser +1, 0, -1."""
    for nombre in listar_estrategias():
        est = obtener_estrategia(nombre)
        señales = est.generar_senales(df_oscilante)
        valores = set(señales.dropna().unique())
        assert valores.issubset({-1, 0, 1}), f"{nombre} generó valores raros: {valores}"


def test_senales_mismo_indice(df_oscilante):
    """Las señales deben tener el mismo índice que el df."""
    for nombre in listar_estrategias():
        est = obtener_estrategia(nombre)
        señales = est.generar_senales(df_oscilante)
        assert len(señales) == len(df_oscilante)
        assert señales.index.equals(df_oscilante.index)


# ---------------------------------------------------------------------------
# Tests Cruce SMA
# ---------------------------------------------------------------------------
def test_cruce_sma_genera_senales(df_oscilante):
    est = EstrategiaCruceSMA(sma_rapida=10, sma_lenta=30)
    señales = est.generar_senales(df_oscilante)
    assert (señales != 0).sum() > 0


def test_cruce_sma_tendencia_alcista(df_alcista):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=20)
    señales = est.generar_senales(df_alcista)
    # En tendencia alcista, más longs que shorts
    longs = (señales == 1).sum()
    shorts = (señales == -1).sum()
    assert longs >= shorts


# ---------------------------------------------------------------------------
# Tests RSI + SMA
# ---------------------------------------------------------------------------
def test_rsi_sma_genera_senales(df_oscilante):
    est = EstrategiaRSISMA(rsi_len=14, rsi_sobrev=30, rsi_sobrec=70, sma_tendencia=50)
    señales = est.generar_senales(df_oscilante)
    assert len(señales) == len(df_oscilante)


# ---------------------------------------------------------------------------
# Tests MACD
# ---------------------------------------------------------------------------
def test_macd_genera_senales(df_oscilante):
    est = EstrategiaMACD(fast=12, slow=26, signal=9)
    señales = est.generar_senales(df_oscilante)
    assert (señales != 0).sum() > 0


# ---------------------------------------------------------------------------
# Tests Bollinger
# ---------------------------------------------------------------------------
def test_bollinger_genera_senales(df_oscilante):
    est = EstrategiaBollinger(longitud=20, desviaciones=2.0)
    señales = est.generar_senales(df_oscilante)
    assert (señales != 0).sum() > 0


# ---------------------------------------------------------------------------
# Tests EMA Tendencia
# ---------------------------------------------------------------------------
def test_ema_tendencia_alcista(df_alcista):
    est = EstrategiaEMATendencia(ema_rapida=10, ema_lenta=30)
    señales = est.generar_senales(df_alcista)
    longs = (señales == 1).sum()
    shorts = (señales == -1).sum()
    assert longs >= shorts


# ---------------------------------------------------------------------------
# Tests Custom
# ---------------------------------------------------------------------------
def test_custom_rsi_precio(df_oscilante):
    est = EstrategiaCustom(
        c1_tipo="RSI < X", c1_valor=30,
        operador="Y",
        c2_tipo="Precio > SMA", c2_valor=50,
    )
    señales = est.generar_senales(df_oscilante)
    assert len(señales) == len(df_oscilante)


def test_custom_operador_o(df_oscilante):
    est = EstrategiaCustom(
        c1_tipo="RSI < X", c1_valor=30,
        operador="O",
        c2_tipo="RSI > X", c2_valor=70,
    )
    señales = est.generar_senales(df_oscilante)
    # Con "O", hay más señales que con "Y"
    est_Y = EstrategiaCustom(
        c1_tipo="RSI < X", c1_valor=30,
        operador="Y",
        c2_tipo="RSI > X", c2_valor=70,
    )
    señales_Y = est_Y.generar_senales(df_oscilante)
    assert (señales != 0).sum() >= (señales_Y != 0).sum()


def test_custom_tipo_invalido(df_oscilante):
    est = EstrategiaCustom(c1_tipo="Inventado", c1_valor=1)
    with pytest.raises(ValueError, match="Tipo de condición desconocido"):
        est.generar_senales(df_oscilante)


# ---------------------------------------------------------------------------
# Tests factory
# ---------------------------------------------------------------------------
def test_factory_pasa_kwargs():
    est = obtener_estrategia("cruce_sma", sma_rapida=5, sma_lenta=15)
    assert isinstance(est, EstrategiaCruceSMA)
    assert est.sma_rapida == 5
    assert est.sma_lenta == 15