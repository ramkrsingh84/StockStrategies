import streamlit as st
import pandas as pd
import yfinance as yf
from supabase import create_client
from core.nifty200_rsi_analyzer import Nifty200RSIAnalyzer

# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

# 🔑 Supabase connection from Streamlit secrets
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# ✅ Loader function
def load_ohlc_to_supabase(tickers, days=90):
    for ticker in tickers:
        try:
            data = yf.download(ticker + ".NS", period=f"{days}d", interval="1d")[["Open","High","Low","Close","Volume"]]
            if data.empty:
                continue
            data = data.reset_index()
            for _, row in data.iterrows():
                supabase.table("ohlc_data").upsert({
                    "ticker": ticker + ".NS",
                    "trade_date": row["Date"].date().isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                }).execute()
                if resp.error:
                    st.error(f"Supabase error for {ticker}: {resp.error}")
        except Exception as e:
            st.error(f"Error loading {ticker}: {e}")

# 🚀 Streamlit UI
st.title("📈 Nifty200 RSI Strategy")

# Placeholder: replace with Google Sheet connector
nifty200_df = pd.DataFrame({
    "Ticker": ["RELIANCE", "HDFCBANK", "INFY"],
    "PEG": [1.2, 0.9, "NA"]
})

# Button 1: Load OHLC data
if st.button("📥 Load OHLC Data into Supabase"):
    load_ohlc_to_supabase(nifty200_df["Ticker"].tolist())
    st.success("✅ OHLC data loaded into Supabase")

# Button 2: Run RSI strategy
if st.button("⚡ Run RSI Buy Signal Strategy"):
    analyzer = Nifty200RSIAnalyzer(supabase)
    summary_df = analyzer.analyze_buy(nifty200_df)
    if not summary_df.empty:
        st.subheader("📊 RSI Buy Signals")
        st.dataframe(
            summary_df.style.format({
                "RSI": "{:.2f}",
                "PEG": "{:.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("No RSI triggers found today.")