import streamlit as st
import pandas as pd
#import matplotlib.pyplot as plt
#import numpy as np
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col

# 🔐 Session protection
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")

st.set_page_config(page_title="Profit Realizarion", layout="wide")
st.title("📈 Profit Realization")

# 🌀 Load all portfolios
all_portfolios = []
for strategy, config in STRATEGY_CONFIG.items():
    runner = StrategyRunner(strategy, config)
    df = runner.portfolio_mgr.load(config["portfolio_tab"])
    df["Strategy"] = strategy
    all_portfolios.append(df)

portfolio_df = pd.concat(all_portfolios, ignore_index=True)

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