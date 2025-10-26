import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col
from core.utils import refresh_all_sheets
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
        st.subheader("📊 Unified Active Portfolio")

        # 🔄 Refresh button
        if st.button("🔄 Refresh Portfolio Data"):
            refresh_all_sheets(STRATEGY_CONFIG)  # triggers dummy edit in "Refresh" sheet
            st.cache_data.clear()
            st.session_state["last_refresh"] = pd.Timestamp.now()

        # ⏱️ Show last refresh time
        last_refresh = st.session_state.get("last_refresh", pd.Timestamp.now())
        st.caption(f"Last refreshed: {last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

        # 🌀 Load and merge all portfolios
        with st.spinner("Loading portfolio data..."):
            all_portfolios = []
            for strategy, config in STRATEGY_CONFIG.items():
                runner = StrategyRunner(strategy, config)
                df = runner.portfolio_mgr.load(config["portfolio_tab"])
                df["Strategy"] = strategy
                all_portfolios.append(df)

            portfolio_df = pd.concat(all_portfolios, ignore_index=True)

        # ✅ Active holdings only
        active_df = portfolio_df[portfolio_df[col("sell_date")].isna()].copy()

        # ✅ Run SELL analysis
        analyzer = list(STRATEGY_CONFIG.values())[0]["analyzer_class"]()
        analyzer.analyze_sell(active_df)
        sell_df = pd.DataFrame(analyzer.signal_log)
        sell_df = sell_df[sell_df["Signal"] == "SELL"]

        # ✅ Merge SELL triggers into active portfolio
        merged = active_df.merge(
            sell_df[[col("ticker"), "Signal", "P&L %", "Price"]],
            how="left",
            on=col("ticker")
        )
        merged["Highlight"] = merged["Signal"].apply(lambda x: "SELL" if x == "SELL" else "NORMAL")

        show_only_sell = st.checkbox("🔻 Show only SELL-triggered holdings")
        filtered_df = merged[merged["Highlight"] == "SELL"] if show_only_sell else merged

        def highlight_sell(row):
            return ["background-color: #ffe6e6" if row["Highlight"] == "SELL" else "" for _ in row]

        styled_df = filtered_df.style.apply(highlight_sell, axis=1)
        st.dataframe(styled_df, width="stretch")

        # 💰 Realized profit summary from sold holdings
        sold_df = portfolio_df[portfolio_df[col("sell_date")].notna()].copy()
        sell_price_col = "Sell Price"

        if sell_price_col not in sold_df.columns:
            st.warning("⚠️ 'Sell Price' column missing in portfolio. Cannot compute realized profit.")
        else:
            sold_df["Investment"] = sold_df[col("buy_price")] * sold_df[col("buy_qty")]
            sold_df["RealizedValue"] = sold_df[sell_price_col] * sold_df[col("buy_qty")]

            total_investment = sold_df["Investment"].sum()
            total_realized = sold_df["RealizedValue"].sum()
            total_profit = total_realized - total_investment
            profit_pct = (total_profit / total_investment * 100) if total_investment > 0 else 0
            
            # ✅ Load surcharges and sum all charges (no Buy/Sell filter)
            surcharge_df = load_surcharges("Surcharges")
            total_surcharge = surcharge_df["Charges"].sum() if "Charges" in surcharge_df.columns else 0

            net_profit = total_profit - total_surcharge
            net_profit_pct = (net_profit / total_investment * 100) if total_investment > 0 else 0

            summary_df = pd.DataFrame({
                "Metric": ["Total Investment (Sold)", "Realized Value", "Profit Earned", "Profit %", "Total Surcharges", "Net Profit", "Net Profit %" ],
                "Value": [
                    f"₹{total_investment:,.2f}",
                    f"₹{total_realized:,.2f}",
                    f"₹{total_profit:,.2f}",
                    f"{profit_pct:.2f}%"
                    f"₹{total_surcharge:,.2f}",
                    f"₹{net_profit:,.2f}",
                    f"{net_profit_pct:.2f}%"
                ]
            })

            st.subheader("💰 Realized Profit Summary")
            st.table(summary_df)

