"""
app.py
======
Interfaz visual del estudio de criptomonedas.

Ejecutar:
---------
    cd ~/proyectosPython/estudio_criptomonedas
    source .env/bin/activate
    streamlit run python/ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROYECTO / "python"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data_loader import DataLoader
from src.estrategias import obtener_estrategia, listar_estrategias
from src.backtest import Backtest
from src.estrategia_custom import (
    compilar_estrategia_usuario,
    ErrorSeguridad,
    ErrorCompilacion,
    ErrorEjecucion,
    PLANTILLAS,
)


# ============================================================================
# Logging (terminal + logs/app.log)
# ============================================================================
import logging
import time
import traceback
from contextlib import contextmanager


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("estudio")
    if not logger.handlers:  # Streamlit re-ejecuta el script: no duplicar handlers
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        carpeta = RAIZ_PROYECTO / "logs"
        carpeta.mkdir(exist_ok=True)
        fh = logging.FileHandler(carpeta / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.propagate = False
    return logger


log = _get_logger()

# Excepciones de control de Streamlit (no son errores reales)
_CONTROL = ("RerunException", "StopException")


@contextmanager
def bloque(nombre: str):
    """Registra entrada/salida/errores de un bloque (p. ej. una pestaña)."""
    t0 = time.perf_counter()
    log.debug("▶ %s", nombre)
    try:
        yield
    except BaseException as e:
        if type(e).__name__ in _CONTROL:
            log.debug("⏹ %s interrumpido por %s", nombre, type(e).__name__)
        else:
            log.error("✖ %s FALLÓ: %r\n%s", nombre, e, traceback.format_exc())
        raise
    else:
        log.debug("✔ %s (%.0f ms)", nombre, (time.perf_counter() - t0) * 1000)


# ============================================================================
# Configuración de página
# ============================================================================
st.set_page_config(
    page_title="Estudio Criptomonedas",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# Estado de sesión (inicialización)
# ============================================================================
_DEFAULTS = {
    "usar_custom": False,
    "codigo_custom": PLANTILLAS["Cruce SMA"],
    "ejecutar_ahora": False,      # flag persistente para disparar backtest
    "backtest_hecho": False,       # para saber si ya hay resultado que mostrar
}
for key, valor in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = valor

st.session_state["_n_runs"] = st.session_state.get("_n_runs", 0) + 1
log.info("=" * 18 + " RERUN #%d " + "=" * 18, st.session_state["_n_runs"])
log.info(
    "estado inicial: ejecutar_ahora=%s backtest_hecho=%s usar_custom=%s tiene_resultado=%s",
    st.session_state["ejecutar_ahora"], st.session_state["backtest_hecho"],
    st.session_state["usar_custom"], "resultado_actual" in st.session_state,
)


# ============================================================================
# Estilos
# ============================================================================
st.markdown("""
    <style>
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.25rem 0;
    }
    .stMetric > label { font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# Cache de datos
# ============================================================================
@st.cache_data(show_spinner="Descargando datos...")
def cargar_datos(exchange: str, simbolo: str, timeframe: str, desde: str, hasta: str):
    log.info("cargar_datos: CACHE MISS -> descargando %s %s %s..%s (%s)", simbolo, timeframe, desde, hasta, exchange)
    dl = DataLoader(exchange=exchange)
    return dl.cargar(simbolo, timeframe, desde, hasta)


@st.cache_data(show_spinner="Ejecutando backtest...")
def ejecutar_backtest_cached(
    exchange: str, simbolo: str, timeframe: str, desde: str, hasta: str,
    nombre_estrategia: str, params_estrategia: tuple,
    capital: float, comision: float, slippage: float,
    modo_riesgo: str, sl_pct: float, tp_pct: float,
    atr_mult_sl: float, atr_mult_tp: float,
    permitir_longs: bool, permitir_shorts: bool,
    usar_custom: bool = False,
    codigo_custom: str = "",
):
    log.info("ejecutar_backtest_cached: CACHE MISS -> calculando (custom=%s, estrategia=%s)", usar_custom, nombre_estrategia)
    df = cargar_datos(exchange, simbolo, timeframe, desde, hasta)

    if usar_custom and codigo_custom.strip():
        est = compilar_estrategia_usuario(codigo_custom)
    else:
        params_dict = dict(params_estrategia)
        est = obtener_estrategia(nombre_estrategia, **params_dict)

    bt = Backtest(
        df=df,
        estrategia=est,
        capital_inicial=capital,
        comision_pct=comision,
        slippage_pct=slippage,
        riesgo={
            "modo": modo_riesgo,
            "sl_pct": sl_pct, "tp_pct": tp_pct,
            "atr_mult_sl": atr_mult_sl, "atr_mult_tp": atr_mult_tp,
            "riesgo_pct": 2.0,
        },
        permitir_longs=permitir_longs,
        permitir_shorts=permitir_shorts,
    )
    res = bt.ejecutar()
    log.info(
        "backtest calculado: tipo=%s trades=%s atributos=%s",
        type(res).__name__, len(getattr(res, "trades", []) or []),
        sorted(getattr(res, "__dict__", {}).keys()),
    )
    return res


# ============================================================================
# SIDEBAR (configuración)
# ============================================================================
st.sidebar.title("⚙️ Configuración")

# --- Activo ---
st.sidebar.header("1️⃣ Activo")
exchange = st.sidebar.selectbox(
    "Exchange", ["binance", "kraken", "coinbase", "bybit", "okx"], index=0,
)
simbolo = st.sidebar.text_input("Símbolo (formato ccxt)", value="BTC/USDT")
col1, col2 = st.sidebar.columns(2)
with col1:
    desde = st.date_input("Desde", value=pd.Timestamp("2024-01-01"))
with col2:
    hasta = st.date_input("Hasta", value=pd.Timestamp("2024-12-31"))
timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=2)

# --- Estrategia ---
st.sidebar.header("2️⃣ Estrategia")

if st.session_state["usar_custom"]:
    st.sidebar.warning("🛠️ Usando estrategia CUSTOM del editor")
    estrategia_nombre = "custom"
    params = {}
    # No mostrar los parámetros de la estrategia común
else:
    estrategia_nombre = st.sidebar.selectbox(
        "Tipo",
        listar_estrategias(),
        format_func=lambda x: x.replace("_", " ").title(),
    )
    st.sidebar.markdown("**Parámetros**")
    params = {}
    if estrategia_nombre == "cruce_sma":
        params["sma_rapida"] = st.sidebar.number_input("SMA rápida", 2, 500, 20)
        params["sma_lenta"]  = st.sidebar.number_input("SMA lenta",  3, 500, 50)
    elif estrategia_nombre == "ema_tendencia":
        params["ema_rapida"] = st.sidebar.number_input("EMA rápida", 2, 500, 20)
        params["ema_lenta"]  = st.sidebar.number_input("EMA lenta",  3, 500, 50)
    elif estrategia_nombre == "rsi_sma":
        params["rsi_len"]       = st.sidebar.number_input("RSI periodo", 2, 100, 14)
        params["rsi_sobrev"]    = st.sidebar.number_input("RSI sobreventa", 1, 50, 30)
        params["rsi_sobrec"]    = st.sidebar.number_input("RSI sobrecompra", 50, 99, 70)
        params["sma_tendencia"] = st.sidebar.number_input("SMA tendencia", 10, 500, 200)
    elif estrategia_nombre == "macd":
        params["fast"]   = st.sidebar.number_input("MACD fast", 2, 100, 12)
        params["slow"]   = st.sidebar.number_input("MACD slow", 3, 200, 26)
        params["signal"] = st.sidebar.number_input("MACD señal", 2, 100, 9)
    elif estrategia_nombre == "bollinger":
        params["longitud"]     = st.sidebar.number_input("Periodos BB", 5, 200, 20)
        params["desviaciones"] = st.sidebar.number_input("Desviaciones", 0.5, 5.0, 2.0, step=0.1)
    elif estrategia_nombre == "custom":
        st.sidebar.markdown("**Condición 1**")
        params["c1_tipo"]  = st.sidebar.selectbox("C1 tipo", [
            "RSI < X", "RSI > X", "Precio > SMA", "Precio < SMA", "MACD cruza señal",
        ], key="c1_tipo")
        params["c1_valor"] = st.sidebar.number_input("C1 valor", 0.0, 1000.0, 30.0)
        params["operador"] = st.sidebar.selectbox("Operador", ["Y", "O"])
        st.sidebar.markdown("**Condición 2**")
        params["c2_tipo"]  = st.sidebar.selectbox("C2 tipo", [
            "RSI < X", "RSI > X", "Precio > SMA", "Precio < SMA", "MACD cruza señal",
        ], key="c2_tipo")
        params["c2_valor"] = st.sidebar.number_input("C2 valor", 0.0, 1000.0, 200.0)

# --- Direcciones ---
st.sidebar.header("3️⃣ Direcciones")
col1, col2 = st.sidebar.columns(2)
with col1:
    permitir_longs = st.checkbox("Largos", value=True)
with col2:
    permitir_shorts = st.checkbox("Cortos", value=False)

# --- Riesgo ---
st.sidebar.header("4️⃣ Riesgo")
modo_riesgo = st.sidebar.selectbox(
    "Modo SL/TP", ["porcentaje", "atr", "ninguno"],
    format_func=lambda x: x.title(),
)
if modo_riesgo == "porcentaje":
    sl_pct = st.sidebar.number_input("SL %", 0.1, 50.0, 2.0, step=0.1)
    tp_pct = st.sidebar.number_input("TP %", 0.1, 100.0, 4.0, step=0.1)
    atr_mult_sl, atr_mult_tp = 1.5, 3.0
elif modo_riesgo == "atr":
    atr_mult_sl = st.sidebar.number_input("ATR mult SL", 0.5, 5.0, 1.5, step=0.1)
    atr_mult_tp = st.sidebar.number_input("ATR mult TP", 0.5, 10.0, 3.0, step=0.1)
    sl_pct, tp_pct = 2.0, 4.0
else:
    sl_pct = tp_pct = 0.0
    atr_mult_sl = atr_mult_tp = 0.0

# --- Costes ---
st.sidebar.header("5️⃣ Costes")
capital  = st.sidebar.number_input("Capital inicial ($)", 100.0, 1_000_000.0, 10_000.0, step=100.0)
comision = st.sidebar.number_input("Comisión %", 0.0, 2.0, 0.1, step=0.01)
slippage = st.sidebar.number_input("Slippage %", 0.0, 2.0, 0.05, step=0.01)

# --- Botón ejecutar ---
st.sidebar.markdown("---")

_clic_ejecutar = st.sidebar.button("🚀 Ejecutar Backtest", type="primary", width="stretch")
log.debug("sidebar: boton Ejecutar -> %s", _clic_ejecutar)
if _clic_ejecutar:
    log.info("sidebar: CLIC en Ejecutar Backtest -> ejecutar_ahora=True")
    st.session_state["ejecutar_ahora"] = True

if st.session_state["usar_custom"]:
    st.sidebar.success("🛠️ Estrategia custom ACTIVA")
    _clic_desactivar = st.sidebar.button("❌ Desactivar custom", width="stretch")
    log.debug("sidebar: boton Desactivar custom -> %s", _clic_desactivar)
    if _clic_desactivar:
        log.info("sidebar: CLIC en Desactivar custom")
        st.session_state["usar_custom"] = False
        st.session_state["ejecutar_ahora"] = True
        st.rerun()


# ============================================================================
# ÁREA PRINCIPAL
# ============================================================================
st.title("📈 Estudio de Criptomonedas")
st.caption(f"Backtest sobre **{simbolo}** en **{exchange}** — {timeframe}")


# ---------------------------------------------------------------------------
# Pestañas (definidas arriba para que los botones del editor puedan disparar)
# ---------------------------------------------------------------------------
tab_custom, tab_grafico, tab_señales, tab_equity, tab_trades, tab_detalles = st.tabs([
    "🛠️ Estrategia Custom",
    "📈 Precio + operaciones",
    "🎯 Señales crudas",
    "💰 Equity",
    "📋 Trades",
    "🔬 Detalles",
])


# ---------------------------------------------------------------------------
# Tab 0: Editor de estrategia custom
# ---------------------------------------------------------------------------
with tab_custom, bloque("tab_custom"):
    st.markdown("### 🛠️ Editor de estrategia en Python")
    st.caption(
        "Escribe tu propia estrategia. Debe definir `generar_senales(df)` "
        "y devolver una `pd.Series` con +1 (long), 0 (nada), -1 (short)."
    )

    if st.session_state["usar_custom"]:
        st.success("✅ Esta estrategia custom está ACTIVA en el backtest actual.")
    else:
        st.info("ℹ️ La estrategia custom NO está activa. Pulsa 'Usar esta estrategia' para activarla.")

    # Selector de plantilla
    col_plantilla, col_boton = st.columns([3, 1])
    with col_plantilla:
        plantilla_nombre = st.selectbox(
            "Plantilla base", list(PLANTILLAS.keys()), key="plantilla_selector"
        )
    with col_boton:
        st.write("")  # espacio
        if st.button("📋 Cargar plantilla"):
            st.session_state["codigo_custom"] = PLANTILLAS[plantilla_nombre]
            st.rerun()

    # Editor
    codigo_actual = st.text_area(
        "Código Python",
        value=st.session_state["codigo_custom"],
        height=400,
        key="editor_custom",
    )
    # Guardar cambios del editor
    st.session_state["codigo_custom"] = codigo_actual

    # Botones de acción
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        validar = st.button("🔍 Validar", width="stretch")
    with col2:
        usar = st.button("🚀 Usar esta estrategia", type="primary", width="stretch")
    with col3:
        st.caption("Al pulsar 'Usar', se ejecutará el backtest automáticamente con tu código.")

    log.debug("editor: validar=%s usar=%s len(codigo)=%d", validar, usar, len(codigo_actual))
    if validar:
        try:
            compilar_estrategia_usuario(codigo_actual)
            st.success("✓ Código válido y seguro")
        except ErrorSeguridad as e:
            st.error(f"🔒 Error de seguridad:\n\n{e}")
        except ErrorCompilacion as e:
            st.error(f"⚠️ Error de compilación: {e}")
        except Exception as e:
            st.error(f"❌ Error inesperado: {e}")

    if usar:
        log.info("editor: CLIC en Usar esta estrategia -> compilando")
        try:
            compilar_estrategia_usuario(codigo_actual)
            st.session_state["usar_custom"] = True
            st.session_state["codigo_custom"] = codigo_actual
            st.session_state["ejecutar_ahora"] = True
            st.rerun()
        except ErrorSeguridad as e:
            st.error(f"🔒 Error de seguridad:\n\n{e}")
        except ErrorCompilacion as e:
            st.error(f"⚠️ Error de compilación: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")

    # Documentación rápida
    with st.expander("📚 API disponible en tu estrategia"):
        st.markdown("""
        **Datos disponibles:**
        - `df["open"]`, `df["high"]`, `df["low"]`, `df["close"]`, `df["volume"]`
        - `df.index` → timestamps UTC

        **Indicadores (`from src.indicadores import ...`):**
        - `sma(serie, longitud)`, `ema(serie, longitud)`
        - `rsi(serie, longitud)`
        - `macd(serie, fast, slow, signal)`
        - `bollinger(serie, longitud, desv)`
        - `atr(high, low, close, longitud)`

        **Debe devolver:** `pd.Series` con `+1`, `0`, `-1`
        """)


# ---------------------------------------------------------------------------
# Ejecución del backtest (DESPUÉS del editor)
# ---------------------------------------------------------------------------
debe_ejecutar = st.session_state["ejecutar_ahora"]
log.info("decision: debe_ejecutar=%s backtest_hecho=%s", debe_ejecutar, st.session_state["backtest_hecho"])

if not debe_ejecutar and not st.session_state["backtest_hecho"]:
    st.info("👈 Configura los parámetros en la barra lateral y pulsa **Ejecutar Backtest**, "
            "o usa el editor de estrategia custom.")
    log.info("decision: nada que ejecutar ni mostrar -> st.stop()")
    st.stop()


if debe_ejecutar:
    log.info(
        "lanzando backtest: %s %s %s..%s estrategia=%s custom=%s params=%s",
        simbolo, timeframe, desde, hasta, estrategia_nombre,
        st.session_state["usar_custom"], params,
    )
    _t0 = time.perf_counter()
    try:
        resultado = ejecutar_backtest_cached(
            exchange=exchange,
            simbolo=simbolo,
            timeframe=timeframe,
            desde=str(desde),
            hasta=str(hasta),
            nombre_estrategia=estrategia_nombre,
            params_estrategia=tuple(sorted(params.items())),
            capital=capital,
            comision=comision,
            slippage=slippage,
            modo_riesgo=modo_riesgo,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            atr_mult_sl=atr_mult_sl,
            atr_mult_tp=atr_mult_tp,
            permitir_longs=permitir_longs,
            permitir_shorts=permitir_shorts,
            usar_custom=st.session_state["usar_custom"],
            codigo_custom=st.session_state["codigo_custom"],
        )
        _ms = (time.perf_counter() - _t0) * 1000
        log.info(
            "backtest devuelto en %.0f ms (si NO hubo 'CACHE MISS' justo antes, vino de cache) "
            "tipo=%s tiene_señales=%s",
            _ms, type(resultado).__name__, getattr(resultado, "señales", None) is not None,
        )
        st.session_state["resultado_actual"] = resultado
        st.session_state["backtest_hecho"] = True
        st.session_state["ejecutar_ahora"] = False
    except ErrorSeguridad as e:
        st.error(f"🔒 Error de seguridad en tu estrategia custom:\n\n{e}")
        log.error("backtest FALLÓ: %r", e, exc_info=True)
        st.session_state["ejecutar_ahora"] = False
        st.stop()
    except ErrorCompilacion as e:
        st.error(f"⚠️ Error de compilación:\n\n{e}")
        log.error("backtest FALLÓ: %r", e, exc_info=True)
        st.session_state["ejecutar_ahora"] = False
        st.stop()
    except ErrorEjecucion as e:
        st.error(f"💥 Error durante la ejecución:\n\n{e}")
        log.error("backtest FALLÓ: %r", e, exc_info=True)
        st.session_state["ejecutar_ahora"] = False
        st.stop()
    except Exception as e:
        st.error(f"❌ Error ejecutando backtest: {e}")
        st.exception(e)
        log.error("backtest FALLÓ: %r", e, exc_info=True)
        st.session_state["ejecutar_ahora"] = False
        st.stop()

resultado = st.session_state.get("resultado_actual")
log.info("resultado_actual en session_state: %s", "SI" if resultado is not None else "NO")
if resultado is None:
    log.warning("sin resultado -> st.stop()")
    st.stop()


# ---------------------------------------------------------------------------
# Métricas principales
# ---------------------------------------------------------------------------
m = resultado.metricas

st.markdown("### 📊 Métricas principales")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Retorno total", f"{m['retorno_total_pct']:+.2f}%")
col2.metric("Capital final", f"${m['capital_final']:,.0f}")
col3.metric("Nº trades", m["num_trades"])
col4.metric("Winrate", f"{m['winrate_pct']:.1f}%")
col5.metric("Max DD", f"{m['max_drawdown_pct']:.1f}%")
col6.metric("Sharpe", f"{m['sharpe']:.2f}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("CAGR", f"{m['cagr_pct']:+.2f}%")
col2.metric("Profit Factor", str(m["profit_factor"]))
col3.metric("Expectancy", f"${m['expectancy']:.2f}")
col4.metric("Duración media", f"{m['duracion_media_velas']:.0f} velas")


# ---------------------------------------------------------------------------
# Cargar df (para gráficos y reportes)
# ---------------------------------------------------------------------------
df = cargar_datos(exchange, simbolo, timeframe, str(desde), str(hasta))
log.info("df listo: %d filas, indice=%s", len(df), type(df.index).__name__)


# ---------------------------------------------------------------------------
# Tab 1: Precio + operaciones (con capa de señales)
# ---------------------------------------------------------------------------
with tab_grafico, bloque("tab_grafico"):
    # --- Selector de visualización ---
    col_opciones1, col_opciones2 = st.columns(2)
    with col_opciones1:
        mostrar_señales = st.checkbox(
            "Mostrar todas las señales de la estrategia",
            value=True,
            help="Señales crudas generadas por la estrategia (antes de SL/TP/cierre)."
        )
    with col_opciones2:
        mostrar_trades = st.checkbox(
            "Mostrar entradas/salidas de operaciones",
            value=True,
            help="Operaciones que realmente se ejecutaron en el backtest."
        )

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Precio",
        ),
        row=1, col=1,
    )

    # --- Capa 1: Señales crudas de la estrategia ---
    if mostrar_señales and getattr(resultado, "señales", None) is not None:
        señales = resultado.señales.reindex(df.index).fillna(0)
        longs_señal  = señales[señales == 1]
        shorts_señal = señales[señales == -1]

        if len(longs_señal) > 0:
            fig.add_trace(
                go.Scatter(
                    x=longs_señal.index,
                    y=df.loc[longs_señal.index, "low"] * 0.995,
                    mode="markers",
                    marker=dict(symbol="circle", size=6, color="rgba(0,255,0,0.5)",
                                line=dict(color="lime", width=1)),
                    name=f"Señal Long ({len(longs_señal)})",
                ),
                row=1, col=1,
            )
        if len(shorts_señal) > 0:
            fig.add_trace(
                go.Scatter(
                    x=shorts_señal.index,
                    y=df.loc[shorts_señal.index, "high"] * 1.005,
                    mode="markers",
                    marker=dict(symbol="circle", size=6, color="rgba(255,0,0,0.5)",
                                line=dict(color="red", width=1)),
                    name=f"Señal Short ({len(shorts_señal)})",
                ),
                row=1, col=1,
            )

    # --- Capa 2: Entradas/salidas reales ---
    if mostrar_trades and resultado.trades:
        entradas_long  = [t for t in resultado.trades if t.direccion == "long"]
        entradas_short = [t for t in resultado.trades if t.direccion == "short"]

        if entradas_long:
            fig.add_trace(
                go.Scatter(
                    x=[t.entrada_fecha for t in entradas_long],
                    y=[t.entrada_precio for t in entradas_long],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=14, color="lime",
                                line=dict(color="darkgreen", width=1)),
                    name=f"Entrada Long ({len(entradas_long)})",
                ),
                row=1, col=1,
            )
        if entradas_short:
            fig.add_trace(
                go.Scatter(
                    x=[t.entrada_fecha for t in entradas_short],
                    y=[t.entrada_precio for t in entradas_short],
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=14, color="red",
                                line=dict(color="darkred", width=1)),
                    name=f"Entrada Short ({len(entradas_short)})",
                ),
                row=1, col=1,
            )

        fig.add_trace(
            go.Scatter(
                x=[t.salida_fecha for t in resultado.trades],
                y=[t.salida_precio for t in resultado.trades],
                mode="markers",
                marker=dict(
                    symbol="x", size=10,
                    color=["lime" if t.pnl > 0 else "red" for t in resultado.trades],
                ),
                name="Salida",
            ),
            row=1, col=1,
        )

    # --- Volumen ---
    colores_vol = ["green" if c >= o else "red"
                   for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], marker_color=colores_vol, name="Volumen"),
        row=2, col=1,
    )

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")

    # --- Estadísticas de señales ---
    if getattr(resultado, "señales", None) is not None:
        señales = resultado.señales.reindex(df.index).fillna(0)
        n_long  = (señales == 1).sum()
        n_short = (señales == -1).sum()
        n_trades = len(resultado.trades)

        st.markdown("**Resumen de señales**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Señales Long",  n_long)
        c2.metric("Señales Short", n_short)
        c3.metric("Trades ejecutados", n_trades)
        c4.metric("Ratio ejecución",
                  f"{n_trades / max(n_long + n_short, 1) * 100:.1f}%")


# ---------------------------------------------------------------------------
# Tab Señales crudas
# ---------------------------------------------------------------------------
with tab_señales, bloque("tab_señales"):
    st.markdown("### 🎯 Señales generadas por la estrategia")
    st.caption("Cada punto es una señal cruda. Muchas señales pueden no generar trade por SL/TP/cierre previo.")

    if getattr(resultado, "señales", None) is None:
        st.warning("No hay señales registradas.")
    else:
        señales = resultado.señales.reindex(df.index).fillna(0)
        longs  = señales[señales == 1]
        shorts = señales[señales == -1]

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Precio",
        ))

        if len(longs) > 0:
            fig.add_trace(go.Scatter(
                x=longs.index,
                y=df.loc[longs.index, "low"] * 0.995,
                mode="markers",
                marker=dict(symbol="triangle-up", size=10, color="lime"),
                name=f"Long ({len(longs)})",
            ))
        if len(shorts) > 0:
            fig.add_trace(go.Scatter(
                x=shorts.index,
                y=df.loc[shorts.index, "high"] * 1.005,
                mode="markers",
                marker=dict(symbol="triangle-down", size=10, color="red"),
                name=f"Short ({len(shorts)})",
            ))

        fig.update_layout(
            height=600,
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, width="stretch")

        # Tabla de señales
        df_señales = pd.DataFrame({
            "Fecha": señales[señales != 0].index,
            "Señal": ["LONG" if s == 1 else "SHORT" for s in señales[señales != 0]],
            "Precio": df.loc[señales[señales != 0].index, "close"].values,
        })
        st.dataframe(df_señales, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Tab 2: Equity
# ---------------------------------------------------------------------------
with tab_equity, bloque("tab_equity"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=resultado.equity_curve.index,
        y=resultado.equity_curve.values,
        mode="lines", fill="tozeroy",
        line=dict(color="royalblue", width=2), name="Equity",
    ))
    fig.add_hline(y=capital, line_dash="dash", line_color="gray",
                  annotation_text="Capital inicial")
    fig.update_layout(
        height=500, title="Curva de equity",
        yaxis_title="Capital ($)", xaxis_title="Fecha",
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    running_max = resultado.equity_curve.cummax()
    dd = (resultado.equity_curve - running_max) / running_max * 100
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", line=dict(color="crimson"), name="Drawdown",
    ))
    fig_dd.update_layout(
        height=300, title="Drawdown (%)",
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_dd, width="stretch")


# ---------------------------------------------------------------------------
# Tab 3: Trades
# ---------------------------------------------------------------------------
with tab_trades, bloque("tab_trades"):
    if not resultado.trades:
        st.warning("No se generaron operaciones con esta configuración.")
    else:
        datos_trades = []
        for i, t in enumerate(resultado.trades, 1):
            datos_trades.append({
                "#": i,
                "Dirección": t.direccion.upper(),
                "Entrada": t.entrada_fecha.strftime("%Y-%m-%d %H:%M"),
                "Precio entrada": f"${t.entrada_precio:,.2f}",
                "Salida": t.salida_fecha.strftime("%Y-%m-%d %H:%M") if t.salida_fecha else "—",
                "Precio salida": f"${t.salida_precio:,.2f}" if t.salida_precio else "—",
                "Motivo": t.motivo_salida,
                "PnL": f"${t.pnl:+,.2f}",
                "PnL %": f"{t.pnl_pct:+.2f}%",
                "Velas": t.duracion_velas,
            })
        df_trades = pd.DataFrame(datos_trades)
        st.dataframe(df_trades, width="stretch", hide_index=True)

        csv = df_trades.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar CSV", data=csv,
            file_name=f"trades_{simbolo.replace('/', '_')}_{timeframe}.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Tab 4: Detalles
# ---------------------------------------------------------------------------
with tab_detalles, bloque("tab_detalles"):
    st.markdown("### Todas las métricas")
    st.json(m)

    st.markdown("### Configuración usada")
    st.json({
        "exchange": exchange, "simbolo": simbolo,
        "timeframe": timeframe, "desde": str(desde), "hasta": str(hasta),
        "estrategia": "CUSTOM (editor)" if st.session_state["usar_custom"] else estrategia_nombre,
        "params_estrategia": params,
        "riesgo": {
            "modo": modo_riesgo, "sl_pct": sl_pct, "tp_pct": tp_pct,
            "atr_mult_sl": atr_mult_sl, "atr_mult_tp": atr_mult_tp,
        },
        "costes": {"capital": capital, "comision": comision, "slippage": slippage},
        "direcciones": {"longs": permitir_longs, "shorts": permitir_shorts},
    })

    st.markdown("### 📥 Exportar reporte")
    if st.button("Generar reporte HTML"):
        from src.reportes import generar_reporte
        with st.spinner("Generando reporte..."):
            config_reporte = {
                "exchange": exchange, "simbolo": simbolo,
                "timeframe": timeframe, "desde": str(desde), "hasta": str(hasta),
                "estrategia": "custom_usuario" if st.session_state["usar_custom"] else estrategia_nombre,
                "params_estrategia": params,
                "riesgo": {
                    "modo": modo_riesgo, "sl_pct": sl_pct, "tp_pct": tp_pct,
                    "atr_mult_sl": atr_mult_sl, "atr_mult_tp": atr_mult_tp,
                },
                "costes": {"capital": capital, "comision": comision, "slippage": slippage},
                "permitir_longs": permitir_longs, "permitir_shorts": permitir_shorts,
            }
            ruta = generar_reporte(resultado, config_reporte, df=df)
            with open(ruta, "r", encoding="utf-8") as f:
                html_contenido = f.read()
            st.download_button(
                "📥 Descargar reporte HTML", data=html_contenido,
                file_name=ruta.name, mime="text/html",
            )
            st.success(f"✓ Reporte generado en `{ruta}`")

log.info("FIN del script: se llegó hasta el final sin cortes")