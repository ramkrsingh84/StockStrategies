import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col
import streamlit_authenticator as stauth
import yaml


# ✅ Load config from YAML file
with open("config.yaml") as file:
    config = yaml.safe_load(file)

# ✅ Create authenticator
authenticator = stauth.Authenticate(
    config,
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"]
)

# ✅ Login widget
name, authentication_status, username = authenticator.login("🔐 Login", "main")

if authentication_status == False:
    st.error("❌ Incorrect username or password")
elif authentication_status == None:
    st.warning("⚠️ Please enter your credentials")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome, {name} 👋")

    # 🔽 Your full dashboard logic goes here


    st.set_page_config(page_title="DMA Signal Dashboard", layout="centered")
    st.title("📈 DMA Signal Dashboard")

    # Session state setup
    if "selected_strategy" not in st.session_state:
        st.session_state.selected_strategy = list(STRATEGY_CONFIG.keys())[0]
    if "results" not in st.session_state:
        st.session_state.results = None

    # Strategy selection
    st.session_state.selected_strategy = st.selectbox(
        "Choose Strategy",
        list(STRATEGY_CONFIG.keys()),
        index=list(STRATEGY_CONFIG.keys()).index(st.session_state.selected_strategy)
    )

    # Run button
    if st.button("Run Strategy"):
        runner = StrategyRunner(st.session_state.selected_strategy, STRATEGY_CONFIG[st.session_state.selected_strategy])
        st.session_state.results = runner.run()

    # Render results
    if st.session_state.results is not None:
        result_df = st.session_state.results

        if result_df.empty:
            st.success("✅ No actionable signals today.")
        else:
            # BUY signals table
            buy_df = result_df[result_df["Signal"] == "BUY"]
            if not buy_df.empty:
                st.subheader("🟢 BUY Signals")
                st.dataframe(buy_df, width="stretch")

            # SELL signals
            sell_df = result_df[result_df["Signal"] == "SELL"].copy()
            sell_df.loc[:, "Signal"] = "SELL"

            # Load portfolio
            portfolio_runner = StrategyRunner(st.session_state.selected_strategy, STRATEGY_CONFIG[st.session_state.selected_strategy])
            portfolio_df = portfolio_runner.portfolio_mgr.load(STRATEGY_CONFIG[st.session_state.selected_strategy]["portfolio_tab"])

            if not portfolio_df.empty:
                st.subheader("📊 Portfolio Summary with SELL Signals")

                # Merge SELL signals into portfolio
                portfolio_df[col("ticker")] = portfolio_df[col("ticker")].astype(str).str.upper()
                merged = portfolio_df.merge(
                    sell_df[[col("ticker"), "Signal", "P&L %", "Price"]],
                    how="left",
                    left_on=col("ticker"),
                    right_on=col("ticker")
                )

                # Add highlight column
                merged["Highlight"] = merged["Signal"].apply(lambda x: "SELL" if x == "SELL" else "NORMAL")

                # SELL filter checkbox
                show_only_sell = st.checkbox("🔻 Show only SELL-triggered holdings")
                filtered_df = merged[merged["Highlight"] == "SELL"] if show_only_sell else merged

                # Styling
                def highlight_sell(row):
                    return ["background-color: #ffe6e6" if row["Highlight"] == "SELL" else "" for _ in row]

                styled_df = filtered_df.style.apply(highlight_sell, axis=1)
                st.dataframe(styled_df, width="stretch")