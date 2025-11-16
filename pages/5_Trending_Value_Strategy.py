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

# 📋 TrendingValueStocks Sheet Summary
summary_df = runner.analyzer.get_sheet_summary()
if not summary_df.empty:
    st.subheader("📋 TrendingValueStocks Buy Table")
    st.dataframe(summary_df.style.format({"Price": "₹{:.2f}", "Final Rank": "{:.2f}"}))


# 🔙 Navigation
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")