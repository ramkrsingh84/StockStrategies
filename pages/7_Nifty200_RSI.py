import json
import pandas as pd
import yfinance as yf
import streamlit as st
from supabase import create_client
from core.fetcher import DataFetcher
from core.runner import StrategyRunner
from config import STRATEGY_CONFIG
from datetime import datetime, timedelta

# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Nifty200 RSI Strategy", layout="wide")
st.title("📈 Nifty200 RSI Strategy Analysis")

# -------------------------------
# OHLC Fetch + Normalize
# -------------------------------
def fetch_ohlc_normalized(ticker: str, days: int = 90):
    df = yf.download(
        ticker,
        period=f"{days}d",
        interval="1d",
        auto_adjust=False,
        group_by="column",
        progress=False
    )
    if df is None or df.empty:
        return None

    # Handle MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=0)
        except Exception:
            pass
        df.columns = ["_".join([str(x) for x in c if x is not None]) for c in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    df = df.reset_index()

    # Find date column
    date_col = next((c for c in ["Date","Datetime","date","datetime"] if c in df.columns), df.columns[0])
    df.columns = [c.lower() for c in df.columns]
    date_col = date_col.lower()

    df["trade_date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")

    # Map OHLC fields
    required_fields = {}
    for field in ["open","high","low","close","volume"]:
        if field in df.columns:
            required_fields[field] = df[field]
        else:
            candidates = [c for c in df.columns if c.endswith(f"_{field}") or c.startswith(f"{field}_")]
            required_fields[field] = df[candidates[0]] if candidates else None

    df = df.where(pd.notnull(df), None)

    payload = pd.DataFrame({
        "ticker": ticker,
        "trade_date": df["trade_date"],
        "open": required_fields["open"],
        "high": required_fields["high"],
        "low": required_fields["low"],
        "close": required_fields["close"],
        "volume": required_fields["volume"],
    })

    payload = payload[payload["trade_date"].notnull()]
    return payload

# -------------------------------
# Supabase Loader
# -------------------------------
def load_ohlc_to_supabase(tickers, days=90):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    progress = st.progress(0)
    status = st.empty()
    success_count, fail_count = 0, 0
    total = len(tickers)

    for i, t in enumerate(tickers, start=1):
        # Normalize ticker: NSE:ACC → ACC.NS
        symbol = t.strip().upper()
        if symbol.startswith("NSE:"):
            symbol = symbol.split("NSE:")[1] + ".NS"
        else:
            symbol = symbol + ".NS"

        status.text(f"Processing {symbol} ({i}/{total})…")
        try:
            payload = fetch_ohlc_normalized(symbol, days=days)
            if payload is None or payload.empty:
                st.warning(f"No OHLC data for {symbol}")
                fail_count += 1
                continue

            rows = payload.to_dict(orient="records")
            if not rows:
                st.warning(f"No valid rows after normalization for {symbol}")
                fail_count += 1
                continue

            resp = supabase.table("ohlc_data").upsert(rows).execute()
            st.write(f"{symbol} → inserted {len(rows)} rows; error:", getattr(resp, "error", None))
            success_count += 1

        except Exception as e:
            st.error(f"Error loading {symbol}: {e}")
            fail_count += 1

        progress.progress(i / total)

    status.empty()
    progress.empty()
    st.success(f"✅ Completed OHLC load. Success: {success_count}, Failed: {fail_count}, Total: {total}")

# -------------------------------
# Buttons
# -------------------------------
if st.button("📥 Load OHLC Data"):
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    if tickers_df.empty or "Ticker" not in tickers_df.columns:
        st.error("No tickers found in Nifty_200 tab.")
        st.stop()

    tickers = tickers_df["Ticker"].dropna().tolist()
    load_ohlc_to_supabase(tickers, days=90)

if st.button("▶️ Run Strategy"):
    runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
    runner.run()
    summary_df = runner.analyzer.get_sheet_summary()

    if not summary_df.empty:
        st.subheader("📋 Nifty200 RSI Buy Table")
        summary_df["RSI"] = pd.to_numeric(summary_df["RSI"], errors="coerce")
        summary_df["PEG"] = pd.to_numeric(summary_df["PEG"], errors="coerce")

        st.dataframe(
            summary_df.style.format({
                "RSI": "{:.2f}",
                "PEG": "{:.2f}"
            }),
            use_container_width=True
        )

with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")