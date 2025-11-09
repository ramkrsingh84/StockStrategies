import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col



st.set_page_config(page_title="FD Benchmark Comparison", layout="wide")
st.title("📈 Strategy vs FD Benchmark")


if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()



# 🌀 Load all portfolios
all_portfolios = []
for strategy, config in STRATEGY_CONFIG.items():
    runner = StrategyRunner(strategy, config)
    df = runner.portfolio_mgr.load(config["portfolio_tab"])
    df["Strategy"] = strategy
    all_portfolios.append(df)

portfolio_df = pd.concat(all_portfolios, ignore_index=True)
sold_df = portfolio_df[portfolio_df[col("sell_date")].notna()].copy()
sell_price_col = "Sell Price"

fd_rate = st.slider("FD Interest Rate (%)", min_value=5.0, max_value=12.0, value=8.0, step=0.5)
show_outperformers_only = st.checkbox("✅ Show only outperformers (Strategy > FD)")

if sell_price_col not in sold_df.columns:
    st.warning("⚠️ 'Sell Price' column missing. Cannot compute benchmark.")
else:
    sold_df["Investment"] = sold_df[col("buy_price")] * sold_df[col("buy_qty")]
    sold_df["RealizedValue"] = sold_df[sell_price_col] * sold_df[col("buy_qty")]
    sold_df[col("buy_date")] = pd.to_datetime(sold_df[col("buy_date")], errors="coerce")
    sold_df[col("sell_date")] = pd.to_datetime(sold_df[col("sell_date")], errors="coerce")
    sold_df = sold_df[sold_df[col("buy_date")].notna() & sold_df[col("sell_date")].notna()]
    sold_df["Days Held"] = (sold_df[col("sell_date")] - sold_df[col("buy_date")]).dt.days.clip(lower=1)

    sold_df["FD Return"] = sold_df["Investment"] * (1 + (fd_rate / 100) * sold_df["Days Held"] / 365)
    sold_df["Strategy Profit"] = sold_df["RealizedValue"] - sold_df["Investment"]
    sold_df["FD Profit"] = sold_df["FD Return"] - sold_df["Investment"]
    sold_df["Excess Profit"] = sold_df["Strategy Profit"] - sold_df["FD Profit"]

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
    benchmark