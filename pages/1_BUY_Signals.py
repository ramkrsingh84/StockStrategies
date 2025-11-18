import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")

st.set_page_config(page_title="BUY Signals", layout="wide")
st.title("🟢 BUY Signals")


# ✅ Tabs setup (only visible after login)
tabs = st.tabs([f"🟢 {strategy} BUY Signals" for strategy in STRATEGY_CONFIG.keys()] )

        
# ✅ BUY signal tabs
for i, strategy in enumerate(STRATEGY_CONFIG.keys()):
    with tabs[i]:
        runner = StrategyRunner(strategy, STRATEGY_CONFIG[strategy])
        result_df = runner.run()
        if "Signal" in result_df.columns:
            buy_df = result_df[result_df["Signal"] == "BUY"]
        else:
            buy_df = pd.DataFrame()

        if buy_df.empty:
            st.success(f"✅ No BUY signals for {strategy}")
        else:
            st.subheader(f"🟢 BUY Signals for {strategy}")
            st.dataframe(buy_df, width="stretch")
        