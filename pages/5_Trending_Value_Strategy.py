import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

# 🧭 Page setup
st.set_page_config(page_title="Trending Value Strategy", layout="wide")
st.title("📈 Trending Value Strategy Analysis")

# 🚀 Run strategy
runner = StrategyRunner("TrendingValue", STRATEGY_CONFIG["TrendingValue"])
runner.run()
analysis_df = runner.analyzer.analysis_df

# 📊 Display results
if analysis_df.empty:
    st.info("No analysis data available.")
else:
    analysis_df = analysis_df.fillna(pd.NA)
    st.dataframe(
        analysis_df[
            ["Ticker", "Final Rank"]
        ].style.format({
            "Final Rank": "{:.2f}"
        }),
        width="stretch"
    )

# 🔙 Navigation
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")