import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Momentum + Value Strategy", layout="wide")
st.title("📊 Momentum + Value Strategy Analysis")

runner = StrategyRunner("MomentumValue", STRATEGY_CONFIG["MomentumValue"])
runner.run()
analysis_df = runner.analyzer.analysis_df

if analysis_df.empty:
    st.info("No analysis data available.")
else:
    st.dataframe(
        analysis_df[
            ["Ticker", "PE", "ROE", "Momentum Rank", "PE Rank", "ROE Rank", "Combined Score", "Signal"]
        ].style.format({
            "PE": "{:.2f}",
            "ROE": "{:.2%}",
            "Momentum Rank": "{:.0f}",
            "PE Rank": "{:.0f}",
            "ROE Rank": "{:.0f}",
            "Combined Score": "{:.2f}"
        }),
        use_container_width=True
    )

with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")