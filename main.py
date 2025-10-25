import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col
import streamlit_authenticator as stauth


st.set_page_config(page_title="DMA Signal Dashboard", layout="centered")

# ✅ Load config from secrets
credentials = {
    "usernames": {
        "ram": {
            "name": st.secrets["credentials"]["usernames"]["ram"]["name"],
            "password": st.secrets["credentials"]["usernames"]["ram"]["password"]
        }
    }
}

cookie_name = st.secrets["cookie"]["name"]
key = st.secrets["cookie"]["key"]
expiry_days = st.secrets["cookie"]["expiry_days"]

# ✅ Create authenticator
authenticator = stauth.Authenticate(
    credentials,
    cookie_name,
    key,
    expiry_days
)

# ✅ Login widget
name, authentication_status, username = authenticator.login("🔐 Login", "main")


# ✅ Handle login states
if authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("⚠️ Please enter your credentials")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome, {name} 👋")

    st.title("📈 DMA Signal Dashboard")

    # ✅ Tabs setup (only visible after login)
    tabs = st.tabs(
        [f"🟢 {strategy} BUY Signals" for strategy in STRATEGY_CONFIG.keys()] +
        ["📊 Portfolio with SELL Triggers"]
    )

    # ✅ BUY signal tabs
    for i, strategy in enumerate(STRATEGY_CONFIG.keys()):
        with tabs[i]:
            runner = StrategyRunner(strategy, STRATEGY_CONFIG[strategy])
            result_df = runner.run()
            buy_df = result_df[result_df["Signal"] == "BUY"]

            if buy_df.empty:
                st.success(f"✅ No BUY signals for {strategy}")
            else:
                st.subheader(f"🟢 BUY Signals for {strategy}")
                st.dataframe(buy_df, width="stretch")

    # ✅ Portfolio tab with SELL triggers
    with tabs[-1]:
        selected_strategy = st.selectbox("Choose strategy for portfolio view", list(STRATEGY_CONFIG.keys()))
        runner = StrategyRunner(selected_strategy, STRATEGY_CONFIG[selected_strategy])
        result_df = runner.run()
        sell_df = result_df[result_df["Signal"] == "SELL"]

        portfolio_df = runner.portfolio_mgr.load(STRATEGY_CONFIG[selected_strategy]["portfolio_tab"])
        portfolio_df[col("ticker")] = portfolio_df[col("ticker")].astype(str).str.upper()

        merged = portfolio_df.merge(
            sell_df[[col("ticker"), "Signal", "P&L %", "Price"]],
            how="left",
            left_on=col("ticker"),
            right_on=col("ticker")
        )
        merged["Highlight"] = merged["Signal"].apply(lambda x: "SELL" if x == "SELL" else "NORMAL")

        show_only_sell = st.checkbox("🔻 Show only SELL-triggered holdings")
        filtered_df = merged[merged["Highlight"] == "SELL"] if show_only_sell else merged

        def highlight_sell(row):
            return ["background-color: #ffe6e6" if row["Highlight"] == "SELL" else "" for _ in row]

        styled_df = filtered_df.style.apply(highlight_sell, axis=1)
        st.subheader("📊 Portfolio Summary")
        st.dataframe(styled_df, width="stretch")
