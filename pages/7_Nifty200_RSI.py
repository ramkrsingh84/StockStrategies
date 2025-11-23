import streamlit as st
import pandas as pd
from core.nifty200_rsi_runner import Nifty200RSIRunner
from config import STRATEGY_CONFIG

# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

# 🧭 Page setup
st.set_page_config(page_title="Nifty200 RSI Strategy", layout="wide")
st.title("📈 Nifty200 RSI Strategy Analysis")

# 🚀 Run strategy
runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
runner.run()
analysis_df = runner.analyzer.analysis_df

# 📋 RSI Sheet Summary
summary_df = runner.analyzer.get_sheet_summary()
if not summary_df.empty:
    st.subheader("📋 Nifty200 RSI Buy Table")

    summary_df["RSI"] = pd.to_numeric(summary_df["RSI"], errors="coerce")
    summary_df["PEG"] = pd.to_numeric(summary_df["PEG"], errors="coerce")

    st.dataframe(
        summary_df.style.format({
            "RSI": "{:.2f}",
            "PEG": "{:.2f}"
        }),
        use_container_width=True
    )

# 🔙 Navigation
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")