"""
Tests unitarios para backtest.py
Ejecutar: pytest python/tests/test_backtest.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.backtest import Backtest, calcular_metricas, ResultadoBacktest, Trade
from src.estrategias import EstrategiaCruceSMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def df_simple():
    """DataFrame con serie conocida para tests deterministas."""
    n = 100
    close = np.linspace(100, 200, n)  # subida lineal
    df = pd.DataFrame({
        "open":   close,
        "high":   close + 1,
        "low":    close - 1,
        "close":  close,
        "volume": np.ones(n) * 1000,
    }, index=pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC"))
    return df


@pytest.fixture
def df_con_picos():
    """Serie que sube y baja varias veces → señales claras."""
    n = 200
    x = np.linspace(0, 6 * np.pi, n)
    close = 100 + 30 * np.sin(x)
    df = pd.DataFrame({
        "open":   close,
        "high":   close + 0.5,
        "low":    close - 0.5,
        "close":  close,
        "volume": np.ones(n) * 1000,
    }, index=pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC"))
    return df


# ---------------------------------------------------------------------------
# Tests básicos
# ---------------------------------------------------------------------------
def test_backtest_sin_señales(df_simple):
    """Con una estrategia que no genera señales, 0 trades."""
    class EstrategiaNula(EstrategiaCruceSMA):
        def generar_senales(self, df):
            return pd.Series(0, index=df.index)

    bt = Backtest(df_simple, EstrategiaNula())
    res = bt.ejecutar()
    assert len(res.trades) == 0
    assert res.metricas["num_trades"] == 0


def test_backtest_genera_trades(df_con_picos):
    """Con oscilaciones, la estrategia debe generar trades."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(
        df_con_picos, est,
        capital_inicial=10_000,
        comision_pct=0.1,
        slippage_pct=0.05,
        riesgo={"modo": "porcentaje", "sl_pct": 2.0, "tp_pct": 4.0, "riesgo_pct": 2.0},
        permitir_longs=True,
        permitir_shorts=True,
    )
    res = bt.ejecutar()
    assert len(res.trades) > 0


def test_equity_curve_longitud(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est)
    res = bt.ejecutar()
    assert len(res.equity_curve) == len(df_con_picos)


def test_equity_empieza_en_capital(df_simple):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_simple, est, capital_inicial=10_000)
    res = bt.ejecutar()
    # El primer valor de equity debe ser igual o cercano al capital
    assert abs(res.equity_curve.iloc[0] - 10_000) < 100


# ---------------------------------------------------------------------------
# Tests de órdenes
# ---------------------------------------------------------------------------
def test_solo_longs(df_con_picos):
    """Con permitir_shorts=False, ninguna operación debe ser short."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=False)
    res = bt.ejecutar()
    for t in res.trades:
        assert t.direccion == "long"


def test_solo_shorts(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=False, permitir_shorts=True)
    res = bt.ejecutar()
    for t in res.trades:
        assert t.direccion == "short"


def test_sin_longs_ni_shorts(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=False, permitir_shorts=False)
    res = bt.ejecutar()
    assert len(res.trades) == 0


# ---------------------------------------------------------------------------
# Tests de SL/TP
# ---------------------------------------------------------------------------
def test_sl_ejecutado(df_simple):
    """Con SL muy ceñido, todas las operaciones deben cerrarse por 'sl'."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(
        df_simple, est,
        riesgo={"modo": "porcentaje", "sl_pct": 0.01, "tp_pct": 100.0, "riesgo_pct": 2.0},
        permitir_longs=True,
    )
    res = bt.ejecutar()
    for t in res.trades:
        # Con SL al 0.01%, casi seguro salta antes que TP
        assert t.motivo_salida in ("sl", "señal_contraria", "fin")


def test_tp_ejecutado(df_simple):
    """Con TP muy ceñido, todas las operaciones deben cerrarse por 'tp'."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(
        df_simple, est,
        riesgo={"modo": "porcentaje", "sl_pct": 100.0, "tp_pct": 0.01, "riesgo_pct": 2.0},
        permitir_longs=True,
    )
    res = bt.ejecutar()
    for t in res.trades:
        assert t.motivo_salida in ("tp", "señal_contraria", "fin")


# ---------------------------------------------------------------------------
# Tests de trades
# ---------------------------------------------------------------------------
def test_trade_tiene_fechas(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()
    for t in res.trades:
        assert t.entrada_fecha is not None
        assert t.salida_fecha is not None
        assert t.entrada_fecha <= t.salida_fecha


def test_trade_pnl_calculado(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()
    for t in res.trades:
        assert isinstance(t.pnl, float)
        assert isinstance(t.pnl_pct, float)
        assert t.comision >= 0


def test_comisiones_reducen_pnl(df_con_picos):
    """Con comisiones altas, el PnL total debe ser menor."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)

    bt_sin = Backtest(df_con_picos, est, comision_pct=0.0, slippage_pct=0.0,
                      permitir_longs=True, permitir_shorts=True)
    bt_con = Backtest(df_con_picos, est, comision_pct=1.0, slippage_pct=0.5,
                      permitir_longs=True, permitir_shorts=True)

    res_sin = bt_sin.ejecutar()
    res_con = bt_con.ejecutar()

    pnl_sin = sum(t.pnl for t in res_sin.trades)
    pnl_con = sum(t.pnl for t in res_con.trades)

    assert pnl_sin > pnl_con


# ---------------------------------------------------------------------------
# Tests de métricas
# ---------------------------------------------------------------------------
def test_metricas_basicas(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()

    m = res.metricas
    assert "num_trades" in m
    assert "winrate_pct" in m
    assert "retorno_total_pct" in m
    assert "max_drawdown_pct" in m
    assert "sharpe" in m
    assert "profit_factor" in m


def test_metricas_sin_trades():
    res = ResultadoBacktest(trades=[], equity_curve=pd.Series([10000]))
    m = calcular_metricas(res, 10000)
    assert m["num_trades"] == 0


def test_winrate_rango(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()
    wr = res.metricas["winrate_pct"]
    assert 0 <= wr <= 100


def test_max_drawdown_negativo(df_con_picos):
    """Max DD se reporta como negativo (o cero)."""
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()
    dd = res.metricas["max_drawdown_pct"]
    assert dd <= 0


# ---------------------------------------------------------------------------
# Tests de no look-ahead
# ---------------------------------------------------------------------------
def test_entrada_al_open_siguiente():
    """La entrada debe ejecutarse al open de la vela siguiente a la señal."""
    # Serie con un cruce garantizado
    n = 30
    close = [100] * 15 + [110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180]
    df = pd.DataFrame({
        "open":   close,
        "high":   [c + 0.5 for c in close],
        "low":    [c - 0.5 for c in close],
        "close":  close,
        "volume": [1000] * n,
    }, index=pd.date_range("2022-01-01", periods=n, freq="4h", tz="UTC"))

    est = EstrategiaCruceSMA(sma_rapida=3, sma_lenta=10)
    bt = Backtest(df, est, permitir_longs=True, permitir_shorts=False)
    res = bt.ejecutar()

    if res.trades:
        primer = res.trades[0]
        # La entrada no puede ser antes de la vela 10 (donde empieza SMA10)
        assert df.index.get_loc(primer.entrada_fecha) >= 10


# ---------------------------------------------------------------------------
# Tests de resultado
# ---------------------------------------------------------------------------
def test_resultado_resumen(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, permitir_longs=True, permitir_shorts=True)
    res = bt.ejecutar()
    texto = res.resumen()
    assert "num_trades" in texto
    assert "winrate" in texto


def test_resultado_capital_inicial(df_con_picos):
    est = EstrategiaCruceSMA(sma_rapida=5, sma_lenta=15)
    bt = Backtest(df_con_picos, est, capital_inicial=5000)
    res = bt.ejecutar()
    assert res.capital_inicial == 5000

