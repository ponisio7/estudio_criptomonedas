"""
Página 1: Selección de activo
Muestra el catálogo de criptos disponibles en Binance y permite explorar.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "python"))

import streamlit as st
import ccxt
import pandas as pd


st.set_page_config(page_title="Selección de activo", page_icon="🪙", layout="wide")
st.title("🪙 Catálogo de activos")

exchange_nombre = st.selectbox("Exchange", ["binance", "kraken", "coinbase"])
busqueda = st.text_input("Filtrar (ej. BTC, ETH)", value="")

if st.button("Cargar mercados"):
    with st.spinner("Consultando exchange..."):
        ex = getattr(ccxt, exchange_nombre)()
        mercados = ex.load_markets()
        filas = []
        for simbolo, info in mercados.items():
            if info.get("spot") and info.get("active"):
                filas.append({
                    "Símbolo": simbolo,
                    "Base": info["base"],
                    "Quote": info["quote"],
                })
        df = pd.DataFrame(filas)

        if busqueda:
            df = df[
                df["Base"].str.contains(busqueda.upper(), na=False)
                | df["Símbolo"].str.contains(busqueda.upper(), na=False)
            ]

        df = df[df["Quote"] == "USDT"].sort_values("Base")
        st.success(f"{len(df)} mercados encontrados")
        st.dataframe(df, width="stretch", hide_index=True)