import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

# 🧭 Page setup
st.set_page_config(page_title="GARP Strategy", layout="wide")
st.title("📊 GARP Strategy Analysis")

# 🚀 Run strategy
runner = StrategyRunner("GARP", STRATEGY_CONFIG["GARP"])
runner.run()
analysis_df = runner.analyzer.analysis_df

# 📊 Display results
summary_df = runner.analyzer.get_sheet_summary()
if summary_df.empty:
    st.info("No analysis data available.")
else:
    summary_df["Price"] = pd.to_numeric(summary_df.get("Price", pd.NA), errors="coerce")
    summary_df["Final Rank"] = pd.to_numeric(summary_df.get("Final Rank", pd.NA), errors="coerce")


    st.dataframe(
        summary_df[["Ticker", "Price", "Final Rank"]].style.format({
            "Price": "₹{:.2f}",
            "Final Rank": "{:.2f}"
        }),
        width="stretch"
    )

# 🔙 Navigation
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")