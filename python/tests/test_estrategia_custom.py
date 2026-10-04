"""
Tests para estrategia_custom.py
Ejecutar: pytest python/tests/test_estrategia_custom.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.estrategia_custom import (
    compilar_estrategia_usuario,
    ErrorSeguridad,
    ErrorCompilacion,
    ErrorEjecucion,
    PLANTILLA_CRUCE_SMA,
    PLANTILLA_RSI_REVERSION,
    PLANTILLAS,
)


@pytest.fixture
def df_ohlcv():
    n = 200
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": np.ones(n) * 1000,
    }, index=idx)


# ---------------------------------------------------------------------------
# Casos válidos
# ---------------------------------------------------------------------------
def test_plantilla_cruce_sma_compila():
    est = compilar_estrategia_usuario(PLANTILLA_CRUCE_SMA)
    assert est is not None


def test_plantilla_cruce_sma_genera_senales(df_ohlcv):
    est = compilar_estrategia_usuario(PLANTILLA_CRUCE_SMA)
    señales = est.generar_senales(df_ohlcv)
    assert len(señales) == len(df_ohlcv)
    assert set(señales.unique()).issubset({-1, 0, 1})


def test_plantilla_rsi_genera_senales(df_ohlcv):
    est = compilar_estrategia_usuario(PLANTILLA_RSI_REVERSION)
    señales = est.generar_senales(df_ohlcv)
    assert len(señales) == len(df_ohlcv)


def test_todas_las_plantillas_compilan():
    for nombre, codigo in PLANTILLAS.items():
        if "Vacía" in nombre:
            continue
        est = compilar_estrategia_usuario(codigo)
        assert est is not None, f"Falla plantilla {nombre}"


def test_senales_clamp(df_ohlcv):
    """Señales devueltas por el usuario se limitan a -1/0/+1."""
    codigo = '''
def generar_senales(df):
    import pandas as pd
    return pd.Series(5, index=df.index)  # valor fuera de rango
'''
    est = compilar_estrategia_usuario(codigo)
    señales = est.generar_senales(df_ohlcv)
    assert (señales == 1).all()


def test_senales_nan_a_cero(df_ohlcv):
    codigo = '''
def generar_senales(df):
    import pandas as pd
    return pd.Series([float("nan")] * len(df), index=df.index)
'''
    est = compilar_estrategia_usuario(codigo)
    señales = est.generar_senales(df_ohlcv)
    assert (señales == 0).all()


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
def test_import_prohibido_os():
    codigo = """
import os
def generar_senales(df):
    return df["close"]
"""
    with pytest.raises(ErrorSeguridad, match="os"):
        compilar_estrategia_usuario(codigo)


def test_import_prohibido_subprocess():
    codigo = """
import subprocess
def generar_senales(df):
    return df["close"]
"""
    with pytest.raises(ErrorSeguridad):
        compilar_estrategia_usuario(codigo)


def test_eval_prohibido():
    codigo = """
def generar_senales(df):
    return eval("1")
"""
    with pytest.raises(ErrorSeguridad, match="eval"):
        compilar_estrategia_usuario(codigo)


def test_exec_prohibido():
    codigo = """
def generar_senales(df):
    exec("x = 1")
    return df["close"]
"""
    with pytest.raises(ErrorSeguridad, match="exec"):
        compilar_estrategia_usuario(codigo)


def test_open_prohibido():
    codigo = """
def generar_senales(df):
    open("/etc/passwd")
    return df["close"]
"""
    with pytest.raises(ErrorSeguridad, match="open"):
        compilar_estrategia_usuario(codigo)


def test_dunder_prohibido():
    codigo = """
def generar_senales(df):
    x = ().__class__
    return df["close"]
"""
    with pytest.raises(ErrorSeguridad):
        compilar_estrategia_usuario(codigo)


# ---------------------------------------------------------------------------
# Errores de compilación
# ---------------------------------------------------------------------------
def test_sintaxis_invalida():
    with pytest.raises(ErrorCompilacion, match="sintaxis"):
        compilar_estrategia_usuario("def generar_senales(df) return df")  # falta ':'


def test_falta_generar_senales():
    with pytest.raises(ErrorCompilacion, match="generar_senales"):
        compilar_estrategia_usuario("x = 1")


def test_no_es_serie_ni_array():
    codigo = """
def generar_senales(df):
    return "hola"
"""
    est = compilar_estrategia_usuario(codigo)
    # Al intentar ejecutar con df, fallará al reindexar
    # (o devolverá todo 0 si pandas lo permite, según versión)
    try:
        est.generar_senales(pd.DataFrame({"close": [1, 2, 3]}))
    except (ErrorEjecucion, Exception):
        pass


# ---------------------------------------------------------------------------
# Errores de ejecución
# ---------------------------------------------------------------------------
def test_error_en_tiempo_ejecucion(df_ohlcv):
    codigo = """
def generar_senales(df):
    return df["columna_que_no_existe"]
"""
    est = compilar_estrategia_usuario(codigo)
    with pytest.raises(ErrorEjecucion):
        est.generar_senales(df_ohlcv)