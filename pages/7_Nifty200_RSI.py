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
                interval="1d",
                auto_adjust=False,          # avoid adjusted columns/multiindex noise
                group_by="column"           # ensure single-level columns
            )[["Open","High","Low","Close","Volume"]]

            if data.empty:
                st.warning(f"No data for {ticker}")
                continue

            # Reset index so Date becomes a column
            data = data.reset_index()

            # 1) Flatten any tuple/multiindex columns to strings
            def flatten(col):
                if isinstance(col, tuple):
                    return "_".join(str(x) for x in col if x is not None)
                return str(col)
            data.columns = [flatten(c) for c in data.columns]

            # 2) Ensure we have the expected column names
            # Some versions produce 'Datetime' or 'Date' column names; unify to 'trade_date'
            if "Date" in data.columns:
                data["trade_date"] = pd.to_datetime(data["Date"]).dt.strftime("%Y-%m-%d")
            elif "Datetime" in data.columns:
                data["trade_date"] = pd.to_datetime(data["Datetime"]).dt.strftime("%Y-%m-%d")
            else:
                # If index name was something else, derive from the first column
                first_col = data.columns[0]
                data["trade_date"] = pd.to_datetime(data[first_col]).dt.strftime("%Y-%m-%d")

            # 3) Replace NaN with None for Supabase compatibility
            data = data.where(pd.notnull(data), None)

            # 4) Keep only the columns we will insert, with lowercase names matching table schema
            payload = pd.DataFrame({
                "ticker": ticker + ".NS",
                "trade_date": data["trade_date"],
                "open": data["Open"],
                "high": data["High"],
                "low": data["Low"],
                "close": data["Close"],
                "volume": data["Volume"],
            })

            # 5) Convert to list of dicts (keys now plain strings)
            rows = payload.to_dict(orient="records")

            if rows:
                resp = supabase.table("ohlc_data").upsert(rows).execute()
                st.write(f"{ticker} → inserted rows: {len(rows)}; response error:", getattr(resp, "error", None))
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