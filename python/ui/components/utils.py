# python/ui/components/utils.py
import streamlit as st

def chart(fig, **kwargs):
    """Wrapper de st.plotly_chart con API moderna."""
    return st.plotly_chart(fig, width="stretch", **kwargs)

def dataframe(df, **kwargs):
    """Wrapper de st.dataframe con API moderna."""
    return st.dataframe(df, width="stretch", **kwargs)