import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner

# 🔐 Session protection
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Momentum + Value Strategy", layout="wide")
st.title("📊 Momentum + Value Strategy")

# 🧪 Run strategy
runner = StrategyRunner("MomentumValue", STRATEGY_CONFIG["MomentumValue"])
buy_df = runner.run()
analyzer = STRATEGY_CONFIG["MomentumValue"]["analyzer_class"]()
analyzer.analyze_buy(buy_df)
signal_df = pd.DataFrame(analyzer.signal_log)

if signal_df.empty:
    st.success("✅ No BUY signals found.")
else:
    st.subheader("🟢 Top Momentum + Value BUY Signals")
    st.dataframe(
        signal_df[["Ticker", "PE", "ROE", "Momentum Rank", "PE Rank", "ROE Rank", "Combined Score"]]
        .style
        .format({
            "PE": "{:.2f}",
            "ROE": "{:.2%}",
            "Momentum Rank": "{:.0f}",
            "PE Rank": "{:.0f}",
            "ROE Rank": "{:.0f}",
            "Combined Score": "{:.2f}"
        }),
        use_container_width=True
    )

# 🏠 Back to Home
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")