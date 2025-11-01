import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col
from core.utils import refresh_all_sheets
import streamlit_authenticator as stauth
import matplotlib.pyplot as plt


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
        ["📊 Portfolio with SELL Triggers", "📈 FD Benchmark Comparison"]
    )

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

    # ✅ Portfolio tab with SELL triggers
    with tabs[-2]:
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
        if "Signal" in sell_df.columns:
            sell_df = sell_df[sell_df["Signal"] == "SELL"]
        else:
            sell_df = pd.DataFrame()  # fallback to empty DataFrame


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

            consolidated["Total Qty"] = consolidated["Total Qty"].astype(int)
            consolidated["Avg Buy Price"] = consolidated["Total Cost"] / consolidated["Total Qty"]
            consolidated["Investment"] = consolidated["Avg Buy Price"] * consolidated["Total Qty"]
            consolidated["Current Value"] = consolidated["Current Price"] * consolidated["Total Qty"]
            consolidated["Profit"] = consolidated["Current Value"] - consolidated["Investment"]
            consolidated["Profit %"] = (consolidated["Profit"] / consolidated["Investment"]) * 100
            consolidated["Target Price (12%)"] = consolidated["Avg Buy Price"] * 1.12

            def highlight_sell(row):
                return [
                    "background-color: #ffe6e6" if row["Highlight"] == "SELL" else ""
                    for _ in row
                ]
            show_only_sell = st.checkbox("🔻 Show only SELL-triggered tickers")
            
            st.subheader("📦 Consolidated Portfolio Summary")
            filtered_consolidated = (
                consolidated[consolidated["Highlight"] == "SELL"]
                if show_only_sell else consolidated
            )

            st.dataframe(
                filtered_consolidated[
                    ["Ticker", "Profit %", "Target Price (12%)", "Total Qty", "Avg Buy Price", "Current Price", "Investment", "Current Value", "Profit", "Highlight", "Strategy"]
                ]
                .style
                .apply(highlight_sell, axis=1)
                .format({
                    "Avg Buy Price": "₹{:.2f}",
                    "Current Price": "₹{:.2f}",
                    "Target Price (12%)": "₹{:.2f}",
                    "Investment": "₹{:.2f}",
                    "Current Value": "₹{:.2f}",
                    "Profit": "₹{:.2f}",
                    "Profit %": "{:.2f}%"
                }),
                width="stretch"
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
            total_investment_all = active_df[col("buy_price")].mul(active_df[col("buy_qty")], fill_value=0).sum()

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
 
        with st.expander("🧪 FD Return vs Realized Value (Sold Only)"):
            st.caption("Validation table for sold entries comparing FD return vs actual realized value.")

            # 🔧 Adjustable FD rate
            fd_rate_sold = st.slider("FD Interest Rate (%)", min_value=5.0, max_value=12.0, value=8.0, step=0.5, key="fd_rate_sold")

            # ✅ Filter sold entries
            sold_df = portfolio_df[portfolio_df[col("sell_date")].notna()].copy()
            sell_price_col = "Sell Price"

            # ✅ Convert dates
            sold_df[col("buy_date")] = pd.to_datetime(sold_df[col("buy_date")], errors="coerce")
            sold_df[col("sell_date")] = pd.to_datetime(sold_df[col("sell_date")], errors="coerce")
            sold_df = sold_df[sold_df[col("buy_date")].notna() & sold_df[col("sell_date")].notna()]

            # ✅ Core calculations
            sold_df["Investment"] = sold_df[col("buy_price")] * sold_df[col("buy_qty")]
            sold_df["RealizedValue"] = sold_df[sell_price_col] * sold_df[col("buy_qty")]
            sold_df["Days Held"] = (sold_df[col("sell_date")] - sold_df[col("buy_date")]).dt.days.clip(lower=1)
            sold_df["FD Return"] = sold_df["Investment"] * (1 + (fd_rate_sold / 100) * sold_df["Days Held"] / 365)
            sold_df["Underperforming FD"] = sold_df["RealizedValue"] < sold_df["FD Return"]

            # ✅ Display validation table
            st.dataframe(
                sold_df[
                    [col("ticker"), col("buy_date"), col("sell_date"), col("buy_price"), col("buy_qty"), sell_price_col, "Investment", "FD Return", "RealizedValue", "Days Held", "Underperforming FD"]
                ]
                .style
                .format({
                    col("buy_price"): "₹{:.2f}",
                    sell_price_col: "₹{:.2f}",
                    "Investment": "₹{:.2f}",
                    "FD Return": "₹{:.2f}",
                    "RealizedValue": "₹{:.2f}",
                    "Days Held": "{:.0f}"
                }),
                width="stretch"
            )
 
    # ✅ FD Benchmark Comparison tab
    with tabs[-1]:
        st.subheader("📈 Strategy vs FD Benchmark")

        # 🔧 Adjustable FD rate
        fd_rate = st.slider("FD Interest Rate (%)", min_value=5.0, max_value=12.0, value=8.0, step=0.5)
        show_outperformers_only = st.checkbox("✅ Show only outperformers (Strategy > FD)")
        

        sold_df = portfolio_df[portfolio_df[col("sell_date")].notna()].copy()
        sell_price_col = "Sell Price"

        if sell_price_col not in sold_df.columns:
            st.warning("⚠️ 'Sell Price' column missing. Cannot compute benchmark.")
        else:
            # ✅ Core calculations
            sold_df["Investment"] = sold_df[col("buy_price")] * sold_df[col("buy_qty")]
            sold_df["RealizedValue"] = sold_df[sell_price_col] * sold_df[col("buy_qty")]

            # ✅ Fix datetime issues
            sold_df[col("buy_date")] = pd.to_datetime(sold_df[col("buy_date")], errors="coerce")
            sold_df[col("sell_date")] = pd.to_datetime(sold_df[col("sell_date")], errors="coerce")
                       
            
            sold_df = sold_df[sold_df[col("buy_date")].notna() & sold_df[col("sell_date")].notna()]

            # ✅ Calculate duration
            sold_df["Days Held"] = (sold_df[col("sell_date")] - sold_df[col("buy_date")]).dt.days.clip(lower=1)

            # ✅ FD return and comparison
            sold_df["FD Return"] = sold_df["Investment"] * (1 + (fd_rate / 100) * sold_df["Days Held"] / 365)
            sold_df["Strategy Profit"] = sold_df["RealizedValue"] - sold_df["Investment"]
            sold_df["FD Profit"] = sold_df["FD Return"] - sold_df["Investment"]
            sold_df["Excess Profit"] = sold_df["Strategy Profit"] - sold_df["FD Profit"]

            # ✅ Group by ticker
            benchmark_df = (
                sold_df.groupby(col("ticker"), as_index=False)
                .agg({
                    "Investment": "sum",
                    "RealizedValue": "sum",
                    "FD Return": "sum",
                    "Strategy Profit": "sum",
                    "FD Profit": "sum",
                    "Excess Profit": "sum"
                })
                .rename(columns={col("ticker"): "Ticker"})
            )


            benchmark_df["Strategy %"] = (benchmark_df["Strategy Profit"] / benchmark_df["Investment"]) * 100
            benchmark_df["FD %"] = (benchmark_df["FD Profit"] / benchmark_df["Investment"]) * 100
            benchmark_df["Excess %"] = benchmark_df["Strategy %"] - benchmark_df["FD %"]

            # ✅ Filter if needed
            if show_outperformers_only:
                benchmark_df = benchmark_df[benchmark_df["Excess Profit"] > 0]

            # ✅ Display table
            st.dataframe(
                benchmark_df[
                    ["Ticker", "Investment", "RealizedValue", "FD Return", "Strategy Profit", "FD Profit", "Excess Profit", "Strategy %", "FD %", "Excess %"]
                ]
                .style
                .format({
                    "Investment": "₹{:.2f}",
                    "RealizedValue": "₹{:.2f}",
                    "FD Return": "₹{:.2f}",
                    "Strategy Profit": "₹{:.2f}",
                    "FD Profit": "₹{:.2f}",
                    "Excess Profit": "₹{:.2f}",
                    "Strategy %": "{:.2f}%",
                    "FD %": "{:.2f}%",
                    "Excess %": "{:.2f}%"
                }),
                width="stretch"
            )

            # 📊 Grouped Bar Chart: Strategy vs FD Profit

            tickers = benchmark_df["Ticker"]
            strategy_profit = benchmark_df["Strategy Profit"]
            fd_profit = benchmark_df["FD Profit"]

            x = np.arange(len(tickers))  # label locations
            width = 0.35  # width of the bars

            fig, ax = plt.subplots(figsize=(10, 6))

            bars1 = ax.bar(x - width/2, strategy_profit, width, label="Strategy", color="green")
            bars2 = ax.bar(x + width/2, fd_profit, width, label="FD", color="gray")

            # ✅ Annotate bars
            for bar in bars1:
                height = bar.get_height()
                ax.annotate(f'₹{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

            for bar in bars2:
                height = bar.get_height()
                ax.annotate(f'₹{height:,.0f}', xy=(bar.get_x() + bar.get_width()/2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

            # ✅ Axis and legend
            ax.set_ylabel("Profit (₹)")
            ax.set_title("Strategy vs FD Profit by Ticker")
            ax.set_xticks(x)
            ax.set_xticklabels(tickers, rotation=45, ha="right")
            ax.legend()

            st.pyplot(fig)


