import streamlit as st
import pandas as pd
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col
from core.utils import refresh_all_sheets

if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()


st.set_page_config(page_title="Portfolio with SELL Triggers", layout="wide")
st.title("📊 Portfolio with SELL Triggers")

if st.button("🔄 Refresh Portfolio Data"):
    refresh_all_sheets(STRATEGY_CONFIG)
    st.cache_data.clear()
    st.session_state["last_refresh"] = pd.Timestamp.now()

last_refresh = st.session_state.get("last_refresh", pd.Timestamp.now())
st.caption(f"Last refreshed: {last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

# 🌀 Load and merge all portfolios
all_portfolios = []
for strategy, config in STRATEGY_CONFIG.items():
    runner = StrategyRunner(strategy, config)
    df = runner.portfolio_mgr.load(config["portfolio_tab"])
    df["Strategy"] = strategy
    all_portfolios.append(df)

portfolio_df = pd.concat(all_portfolios, ignore_index=True)
active_df = portfolio_df[portfolio_df[col("sell_date")].isna()].copy()

# ✅ Run SELL analysis
analyzer = list(STRATEGY_CONFIG.values())[0]["analyzer_class"]()
analyzer.analyze_sell(active_df)
sell_df = pd.DataFrame(analyzer.signal_log)
sell_df = sell_df[sell_df["Signal"] == "SELL"] if "Signal" in sell_df.columns else pd.DataFrame()

# ✅ Merge SELL triggers
if not sell_df.empty and col("ticker") in sell_df.columns and col("ticker") in active_df.columns:
    merged_df = active_df.merge(sell_df[[col("ticker"), "Signal"]], how="left", on=col("ticker"))
    merged_df["Highlight"] = merged_df["Signal"].fillna("NORMAL").apply(lambda x: "SELL" if x == "SELL" else "NORMAL")
else:
    merged_df = active_df.copy()
    merged_df["Highlight"] = "NORMAL"

# ✅ Consolidated summary
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
    return ["background-color: #ffe6e6" if row["Highlight"] == "SELL" else "" for _ in row]

show_only_sell = st.checkbox("🔻 Show only SELL-triggered tickers")
filtered_consolidated = consolidated[consolidated["Highlight"] == "SELL"] if show_only_sell else consolidated

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
    use_container_width=True
)
