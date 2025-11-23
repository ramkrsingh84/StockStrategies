import streamlit as st
import pandas as pd
from core.runner import StrategyRunner
from config import STRATEGY_CONFIG

import yfinance as yf
from supabase import create_client


import json
import time
from datetime import datetime, timedelta
from core.fetcher import DataFetcher  # uses your existing fetcher


# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

# 🧭 Page setup
st.set_page_config(page_title="Nifty200 RSI Strategy", layout="wide")
st.title("📈 Nifty200 RSI Strategy Analysis")


def _normalize_tickers(df):
    """Convert tickers like 'NSE:ACC' → 'ACC.NS' for yfinance."""
    if "Ticker" not in df.columns:
        return []
    tickers = (
        df["Ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"": pd.NA})
        .dropna()
        .unique()
        .tolist()
    )
    normalized = []
    for t in tickers:
        if t.startswith("NSE:"):
            symbol = t.split("NSE:")[1]
            normalized.append(f"{symbol}.NS")
        else:
            # fallback: just append .NS
            normalized.append(f"{t}.NS")
    return normalized

def _fetch_ohlc_for_ticker(ticker_ns: str, days: int = 30):
    """Fetch last N trading days OHLC via yfinance for a '.NS' ticker."""
    end = datetime.today()
    start = end - timedelta(days=days * 2)  # buffer across weekends/holidays
    df = yf.download(ticker_ns, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        return []

    df = df.tail(days)
    records = []
    for trade_dt, row in df.iterrows():
        try:
            records.append({
                "ticker": ticker_ns,
                "trade_date": trade_dt.date().isoformat(),
                "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
                "high": float(row["High"]) if pd.notna(row["High"]) else None,
                "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
                "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            })
        except Exception:
            # Skip malformed rows but continue
            continue
    return records

def _upsert_ohlc_batch(supabase, records):
    """Upsert a batch of records into Supabase ohlc_data."""
    if not records:
        return
    # Upsert honors unique(ticker, trade_date)
    supabase.table("ohlc_data").upsert(records).execute()



# 🚀 Buttons
if st.button("📥 Load OHLC Data"):
    st.info("Reading tickers from DMA_Data → Nifty_200 and loading OHLC into Supabase…")

    df = yf.download("ACC.NS", period="1mo")
    print(df.head())
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    tickers = _normalize_tickers(tickers_df)
    st.write("Normalized tickers:", tickers[:10])

    if not tickers:
        st.error("No valid tickers found in Nifty_200 tab.")
        st.stop()

    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    progress = st.progress(0)
    status = st.empty()
    success_count, fail_count = 0, 0

    total = len(tickers)
    for i, t in enumerate(tickers, start=1):
        status.text(f"Processing {t} ({i}/{total})…")
        try:
            records = _fetch_ohlc_for_ticker(t, days=30)
            if records:
                _upsert_ohlc_batch(supabase, records)
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            fail_count += 1
            st.write(f"⚠️ {t}: {e}")
        progress.progress(i / total)

    status.empty()
    progress.empty()
    st.success(f"✅ Completed OHLC load. Success: {success_count}, Failed: {fail_count}, Total: {total}")

if st.button("🧹 Prune OHLC Data (keep 2 years)"):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    cutoff_date = (datetime.today() - timedelta(days=730)).date().isoformat()

    # Delete rows older than cutoff_date
    supabase.table("ohlc_data").delete().lt("trade_date", cutoff_date).execute()

    st.success(f"✅ Pruned OHLC data, keeping only records since {cutoff_date}")


if st.button("▶️ Run Strategy"):
    runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
    runner.run()
    analysis_df = runner.analyzer.analysis_df

    # 📋 RSI Sheet Summary
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

# 🔙 Navigation
with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")