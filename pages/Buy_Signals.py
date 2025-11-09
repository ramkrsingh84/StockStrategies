import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="BUY Signals", layout="wide")
st.title("🟢 BUY Signals")


for strategy in STRATEGY_CONFIG:
    st.subheader(f"📈 {strategy}")
    runner = StrategyRunner(strategy, STRATEGY_CONFIG[strategy])
    result_df = runner.run()
    buy_df = result_df[result_df["Signal"] == "BUY"] if "Signal" in result_df.columns else pd.DataFrame()

    if buy_df.empty:
        st.success("✅ No BUY signals")
    else:
        st.dataframe(buy_df, use_container_width=True)
        