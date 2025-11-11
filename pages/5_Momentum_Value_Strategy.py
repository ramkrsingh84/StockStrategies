import streamlit as st
import pandas as pd
import yfinance as yf
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col

# 🔐 Session protection
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Momentum + Value Strategy", layout="wide")
st.title("📊 Momentum + Value Strategy")

# 🔧 Strategy parameters
lookback_days = st.slider("📅 Lookback Period (days)", min_value=30, max_value=252, value=126, step=21)
top_n = st.slider("🔝 Top N Picks", min_value=5, max_value=50, value=10, step=5)

# 📦 Load tickers from Google Sheet
runner = StrategyRunner("MomentumValue", STRATEGY_CONFIG.get("MomentumValue", {}))
ticker_df = runner.portfolio_mgr.load("Nifty200_Tickers")  # Replace with actual tab name
tickers = ticker_df[col("ticker")].dropna().unique().tolist()

if not tickers:
    st.warning("⚠️ No tickers found in Nifty200_Tickers sheet.")
    st.stop()

# 📈 Download price data
with st.spinner("Fetching price data..."):
    price_data = yf.download(tickers, period=f"{lookback_days}d", interval="1d", progress=False)["Adj Close"]
    returns = price_data.pct_change().dropna()
    cumulative_returns = (1 + returns).prod() - 1
    momentum_rank = cumulative_returns.rank(ascending=False)

# 📊 Fetch value metrics
fundamentals = {}
for ticker in tickers:
    try:
        info = yf.Ticker(ticker).info
        pe = info.get("trailingPE", None)
        roe = info.get("returnOnEquity", None)
        fundamentals[ticker] = {"PE": pe, "ROE": roe}
    except Exception:
        fundamentals[ticker] = {"PE": None, "ROE": None}

fundamentals_df = pd.DataFrame(fundamentals).T
fundamentals_df["Momentum Rank"] = momentum_rank

# 🧮 Value ranks
fundamentals_df["PE Rank"] = fundamentals_df["PE"].rank(ascending=True)
fundamentals_df["ROE Rank"] = fundamentals_df["ROE"].rank(ascending=False)

# 🧠 Combined score
fundamentals_df["Combined Score"] = fundamentals_df[["Momentum Rank", "PE Rank", "ROE Rank"]].mean(axis=1)
top_picks = fundamentals_df.sort_values("Combined Score").head(top_n)

# ✅ Display results
st.subheader("🟢 Top Momentum + Value Picks")
st.dataframe(
    top_picks[["PE", "ROE", "Momentum Rank", "PE Rank", "ROE Rank", "Combined Score"]]
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