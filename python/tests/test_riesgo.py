"""
Tests unitarios para riesgo.py
Ejecutar: pytest python/tests/test_riesgo.py -v
"""

import numpy as np
import pandas as pd
import pytest

from src.riesgo import (
    calcular_sl_tp,
    calcular_qty,
    actualizar_trailing_stop,
    agregar_atr,
)


# ---------------------------------------------------------------------------
# Tests calcular_sl_tp
# ---------------------------------------------------------------------------
class TestCalcularSLTP:

    def test_modo_ninguno(self):
        sl, tp = calcular_sl_tp(50000, "long", modo="ninguno")
        assert sl is None
        assert tp is None

    def test_porcentaje_long(self):
        sl, tp = calcular_sl_tp(50000, "long", modo="porcentaje", sl_pct=2, tp_pct=4)
        assert sl == pytest.approx(49000)
        assert tp == pytest.approx(52000)

    def test_porcentaje_short(self):
        sl, tp = calcular_sl_tp(50000, "short", modo="porcentaje", sl_pct=2, tp_pct=4)
        assert sl == pytest.approx(51000)
        assert tp == pytest.approx(48000)

    def test_atr_long(self):
        sl, tp = calcular_sl_tp(
            50000, "long", atr_actual=500, modo="atr",
            atr_mult_sl=1.5, atr_mult_tp=3.0,
        )
        assert sl == pytest.approx(49250)   # 50000 - 1.5*500
        assert tp == pytest.approx(51500)   # 50000 + 3*500

    def test_atr_short(self):
        sl, tp = calcular_sl_tp(
            50000, "short", atr_actual=500, modo="atr",
            atr_mult_sl=1.5, atr_mult_tp=3.0,
        )
        assert sl == pytest.approx(50750)
        assert tp == pytest.approx(48500)

    def test_atr_sin_valor(self):
        """Sin ATR → devuelve None, None."""
        sl, tp = calcular_sl_tp(50000, "long", atr_actual=None, modo="atr")
        assert sl is None
        assert tp is None

    def test_atr_nan(self):
        sl, tp = calcular_sl_tp(50000, "long", atr_actual=np.nan, modo="atr")
        assert sl is None
        assert tp is None

    def test_modo_invalido(self):
        with pytest.raises(ValueError, match="modo SL/TP desconocido"):
            calcular_sl_tp(50000, "long", modo="inventado")

    def test_direccion_invalida(self):
        with pytest.raises(ValueError, match="dirección inválida"):
            calcular_sl_tp(50000, "arriba", modo="porcentaje")


# ---------------------------------------------------------------------------
# Tests calcular_qty
# ---------------------------------------------------------------------------
class TestCalcularQty:

    def test_porcentaje_capital(self):
        qty = calcular_qty(10000, 50000, stop_loss=None,
                           riesgo_pct=10, modo="porcentaje_capital")
        assert qty == pytest.approx(0.02)  # 1000/50000

    def test_riesgo_fijo(self):
        """10.000 capital, 2% riesgo = 200. Entrada 50.000, SL 49.000 (dist 1000).
        qty = 200/1000 = 0.2"""
        qty = calcular_qty(10000, 50000, stop_loss=49000,
                           riesgo_pct=2, modo="riesgo_fijo")
        assert qty == pytest.approx(0.2)

    def test_riesgo_fijo_sin_sl(self):
        """Sin SL → usa porcentaje de capital."""
        qty = calcular_qty(10000, 50000, stop_loss=None,
                           riesgo_pct=10, modo="riesgo_fijo")
        assert qty == pytest.approx(0.02)

    def test_riesgo_fijo_sl_igual_entrada(self):
        """SL = entrada → distancia 0 → usa porcentaje."""
        qty = calcular_qty(10000, 50000, stop_loss=50000,
                           riesgo_pct=10, modo="riesgo_fijo")
        assert qty == pytest.approx(0.02)

    def test_modo_invalido(self):
        with pytest.raises(ValueError, match="modo qty desconocido"):
            calcular_qty(10000, 50000, None, modo="magico")


# ---------------------------------------------------------------------------
# Tests trailing stop
# ---------------------------------------------------------------------------
class TestTrailingStop:

    def test_long_mejora(self):
        sl = actualizar_trailing_stop(51000, 49000, "long", 500)
        assert sl == 50500  # 51000 - 500

    def test_long_no_empeora(self):
        """SL previo mejor → no baja."""
        sl = actualizar_trailing_stop(50500, 50000, "long", 1000)
        assert sl == 50000  # mantiene el mejor

    def test_long_primera_vez(self):
        sl = actualizar_trailing_stop(50000, None, "long", 500)
        assert sl == 49500

    def test_short_mejora(self):
        sl = actualizar_trailing_stop(49000, 51000, "short", 500)
        assert sl == 49500

    def test_short_no_empeora(self):
        sl = actualizar_trailing_stop(49500, 50000, "short", 1000)
        assert sl == 50000

    def test_direccion_invalida(self):
        with pytest.raises(ValueError, match="dirección inválida"):
            actualizar_trailing_stop(50000, None, "arriba", 500)


# ---------------------------------------------------------------------------
# Tests agregar_atr
# ---------------------------------------------------------------------------
def test_agregar_atr():
    n = 100
    np.random.seed(0)
    close = 100 + np.cumsum(np.random.randn(n))
    df = pd.DataFrame({
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": np.ones(n),
    })
    df = agregar_atr(df, longitud=14)
    assert "atr_14" in df.columns
    assert df["atr_14"].dropna().shape[0] > 0
    assert (df["atr_14"].dropna() > 0).all()