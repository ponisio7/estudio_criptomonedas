"""
Tests unitarios para indicadores.py
Ejecutar: pytest python/tests/test_indicadores.py -v
"""

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.indicadores import (
    sma, ema, rsi, macd, bollinger, atr,
    agregar_indicadores, listar_indicadores,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def serie_simple():
    """Serie de 100 valores crecientes del 1 al 100."""
    return pd.Series(np.arange(1, 101, dtype=float))


@pytest.fixture
def df_ohlcv():
    """DataFrame OHLCV sintético de 200 velas."""
    n = 200
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low  = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    volume = np.abs(np.random.randn(n) * 1000) + 100
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=idx)


# ---------------------------------------------------------------------------
# Tests SMA
# ---------------------------------------------------------------------------
def test_sma_longitud(serie_simple):
    resultado = sma(serie_simple, 10)
    assert len(resultado) == len(serie_simple)
    assert resultado.iloc[:9].isna().all()  # primeros 9 NaN
    assert not pd.isna(resultado.iloc[9])


def test_sma_valor_correcto(serie_simple):
    resultado = sma(serie_simple, 5)
    # SMA de 5 primeros = (1+2+3+4+5)/5 = 3
    assert resultado.iloc[4] == pytest.approx(3.0)


def test_sma_serie_constante():
    serie = pd.Series([10.0] * 20)
    resultado = sma(serie, 5)
    assert resultado.iloc[-1] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Tests EMA
# ---------------------------------------------------------------------------
def test_ema_longitud(serie_simple):
    resultado = ema(serie_simple, 10)
    assert len(resultado) == len(serie_simple)


def test_ema_reactiva(serie_simple):
    """EMA reacciona más rápido que SMA ante un cambio."""
    sma_val = sma(serie_simple, 10).iloc[-1]
    ema_val = ema(serie_simple, 10).iloc[-1]
    # En serie creciente, EMA > SMA
    assert ema_val > sma_val


# ---------------------------------------------------------------------------
# Tests RSI
# ---------------------------------------------------------------------------
def test_rsi_rango(serie_simple):
    """RSI debe estar entre 0 y 100."""
    resultado = rsi(serie_simple, 14).dropna()
    assert (resultado >= 0).all()
    assert (resultado <= 100).all()


def test_rsi_serie_creciente():
    """En serie solo creciente, RSI ≈ 100."""
    serie = pd.Series(np.arange(1, 100, dtype=float))
    resultado = rsi(serie, 14).dropna()
    assert resultado.iloc[-1] > 95


def test_rsi_serie_decreciente():
    """En serie solo decreciente, RSI ≈ 0."""
    serie = pd.Series(np.arange(100, 1, -1, dtype=float))
    resultado = rsi(serie, 14).dropna()
    assert resultado.iloc[-1] < 5


# ---------------------------------------------------------------------------
# Tests MACD
# ---------------------------------------------------------------------------
def test_macd_columnas(serie_simple):
    resultado = macd(serie_simple)
    assert set(resultado.columns) == {"macd", "macd_signal", "macd_hist"}


def test_macd_histograma(serie_simple):
    """Histograma = MACD − Señal."""
    resultado = macd(serie_simple).dropna()
    diff = (resultado["macd"] - resultado["macd_signal"]) - resultado["macd_hist"]
    assert diff.abs().max() < 1e-10


# ---------------------------------------------------------------------------
# Tests Bollinger
# ---------------------------------------------------------------------------
def test_bollinger_orden(serie_simple):
    """Superior > Media > Inferior."""
    resultado = bollinger(serie_simple, 20, 2.0).dropna()
    assert (resultado["bb_upper"] > resultado["bb_middle"]).all()
    assert (resultado["bb_middle"] > resultado["bb_lower"]).all()


def test_bollinger_simetria(serie_simple):
    """Media = (Superior + Inferior) / 2."""
    resultado = bollinger(serie_simple, 20, 2.0).dropna()
    media_calculada = (resultado["bb_upper"] + resultado["bb_lower"]) / 2
    diff = (media_calculada - resultado["bb_middle"]).abs().max()
    assert diff < 1e-10


# ---------------------------------------------------------------------------
# Tests ATR
# ---------------------------------------------------------------------------
def test_atr_positivo(df_ohlcv):
    """ATR siempre positivo."""
    resultado = atr(df_ohlcv["high"], df_ohlcv["low"], df_ohlcv["close"], 14).dropna()
    assert (resultado > 0).all()


# ---------------------------------------------------------------------------
# Tests agregar_indicadores
# ---------------------------------------------------------------------------
def test_agregar_indicadores_default(df_ohlcv):
    df = agregar_indicadores(df_ohlcv)
    columnas_esperadas = ["sma_20", "sma_50", "ema_20", "ema_50", "rsi_14", "atr_14"]
    for col in columnas_esperadas:
        assert col in df.columns, f"Falta {col}"


def test_agregar_indicadores_specificos(df_ohlcv):
    df = agregar_indicadores(df_ohlcv, ["sma_10", "rsi_21"])
    assert "sma_10" in df.columns
    assert "rsi_21" in df.columns
    assert "sma_20" not in df.columns


def test_agregar_indicadores_macd(df_ohlcv):
    df = agregar_indicadores(df_ohlcv, ["macd_12_26_9"])
    assert "macd_12_26_9" in df.columns
    assert "macd_signal_12_26_9" in df.columns
    assert "macd_hist_12_26_9" in df.columns


def test_agregar_indicadores_bollinger(df_ohlcv):
    df = agregar_indicadores(df_ohlcv, ["bb_20_2.0"])
    assert "bb_upper_20_2.0" in df.columns
    assert "bb_lower_20_2.0" in df.columns


def test_listar_indicadores():
    lista = listar_indicadores()
    assert "sma" in lista
    assert "ema" in lista
    assert "rsi" in lista
    assert "macd" in lista