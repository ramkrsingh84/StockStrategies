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
            data = yf.download(
                ticker + ".NS",
                period=f"{days}d",
                interval="1d"
            )[["Open","High","Low","Close","Volume"]]

            if data.empty:
                st.warning(f"No data for {ticker}")
                continue

            data = data.reset_index()
            rows = []
            for _, row in data.iterrows():
                rows.append({
                    "ticker": ticker + ".NS",
                    # ✅ FIXED: convert Timestamp to string date
                    "trade_date": pd.to_datetime(row["Date"]).strftime("%Y-%m-%d"),
                    "open": float(row["Open"]) if not pd.isna(row["Open"]) else None,
                    "high": float(row["High"]) if not pd.isna(row["High"]) else None,
                    "low": float(row["Low"]) if not pd.isna(row["Low"]) else None,
                    "close": float(row["Close"]) if not pd.isna(row["Close"]) else None,
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else None
                })

            if rows:
                resp = supabase.table("ohlc_data").upsert(rows).execute()
                st.write(f"{ticker} → Supabase response:", resp)
            else:
                st.warning(f"No valid OHLC rows for {ticker}")

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