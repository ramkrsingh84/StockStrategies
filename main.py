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
        st.subheader("📊 Unified Portfolio Overview")

        # 🔄 Refresh button
        if st.button("🔄 Refresh Portfolio Data"):
            refresh_all_sheets(STRATEGY_CONFIG)
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

        # ✅ Safe SELL trigger merge
        if (
            not sell_df.empty and
            "Signal" in sell_df.columns and
            col("ticker") in sell_df.columns and
            col("ticker") in active_df.columns
        ):
            merged_df = active_df.merge(
                sell_df[[col("ticker"), "Signal"]],
                how="left",
                on=col("ticker")
            )
            merged_df["Highlight"] = merged_df["Signal"].fillna("NORMAL").apply(lambda x: "SELL" if x == "SELL" else "NORMAL")
        else:
            merged_df = active_df.copy()
            merged_df["Highlight"] = "NORMAL"

        # 📦 Consolidated Portfolio Summary
        if not merged_df.empty:
            consolidated = (
                merged_df.copy()
                .assign(weighted_cost=lambda df: df[col("buy_price")] * df[col("buy_qty")])
                .groupby([col("ticker"), "Strategy", "Highlight"], as_index=False)
                .agg({
                    col("buy_qty"): "sum",
                    "weighted_cost": "sum",
                    col("current_price"): "first"
                })
                .rename(columns={
                    col("ticker"): "Ticker",
                    col("buy_qty"): "Total Qty",
                    "weighted_cost": "Total Cost",
                    col("current_price"): "Current Price"
                })
            )

            consolidated["Avg Buy Price"] = consolidated["Total Cost"] / consolidated["Total Qty"]
            consolidated["Investment"] = consolidated["Avg Buy Price"] * consolidated["Total Qty"]
            consolidated["Current Value"] = consolidated["Current Price"] * consolidated["Total Qty"]
            consolidated["Profit"] = consolidated["Current Value"] - consolidated["Investment"]
            consolidated["Profit %"] = (consolidated["Profit"] / consolidated["Investment"]) * 100

            def highlight_sell(row):
                return [
                    "background-color: #ffe6e6" if row["Highlight"] == "SELL" else ""
                    for _ in row
                ]

            st.subheader("📦 Consolidated Portfolio Summary")
            st.dataframe(
                consolidated[
                    ["Ticker", "Strategy", "Total Qty", "Avg Buy Price", "Current Price", "Investment", "Current Value", "Profit", "Profit %", "Highlight"]
                ]
                .style
                .apply(highlight_sell, axis=1)
                .format({
                    "Avg Buy Price": "₹{:.2f}",
                    "Current Price": "₹{:.2f}",
                    "Investment": "₹{:.2f}",
                    "Current Value": "₹{:.2f}",
                    "Profit": "₹{:.2f}",
                    "Profit %": "{:.2f}%"
                }),
                use_container_width=True
            )

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

            # ✅ Load surcharges and sum all charges
            surcharge_df = runner.portfolio_mgr.load_surcharges()
            total_surcharge = surcharge_df["Charges"].sum() if "Charges" in surcharge_df.columns else 0

            net_profit = total_profit - total_surcharge
            net_profit_pct = (net_profit / total_investment * 100) if total_investment > 0 else 0

            # ✅ Add total investment across all holdings
            total_investment_all = portfolio_df[col("buy_price")].mul(portfolio_df[col("buy_qty")], fill_value=0).sum()

            summary_df = pd.DataFrame({
                "Metric": [
                    "Total Investment (All)",
                    "Total Investment (Sold)",
                    "Realized Value",
                    "Profit Earned",
                    "Profit %",
                    "Total Surcharges",
                    "Net Profit",
                    "Net Profit %"
                ],
                "Value": [
                    f"₹{total_investment_all:,.2f}",
                    f"₹{total_investment:,.2f}",
                    f"₹{total_realized:,.2f}",
                    f"₹{total_profit:,.2f}",
                    f"{profit_pct:.2f}%",
                    f"₹{total_surcharge:,.2f}",
                    f"₹{net_profit:,.2f}",
                    f"{net_profit_pct:.2f}%"
                ]
            })

            st.subheader("💰 Realized Profit Summary")
            st.table(summary_df)

