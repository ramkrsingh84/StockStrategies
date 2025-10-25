import streamlit as st
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

st.set_page_config(page_title="DMA Signal Dashboard", layout="wide")
st.title("📈 DMA Signal Dashboard")

selected_strategy = st.selectbox("Choose Strategy", list(STRATEGY_CONFIG.keys()))
run_button = st.button("Run Strategy")

if run_button:
    with st.spinner("Running analysis..."):
        runner = StrategyRunner(selected_strategy, STRATEGY_CONFIG[selected_strategy])
        result_df = runner.run()

    if result_df.empty:
        st.success("✅ No actionable signals today.")
    else:
        st.subheader("📋 Signal Summary")
        st.dataframe(result_df)

        st.subheader("📊 Signal Breakdown")
        buy_df = result_df[result_df["Signal"] == "BUY"]
        sell_df = result_df[result_df["Signal"] == "SELL"]

        if not buy_df.empty:
            st.markdown("### 🟢 BUY Signals")
            st.dataframe(buy_df)

        if not sell_df.empty:
            st.markdown("### 🔴 SELL Signals")
            st.dataframe(sell_df)