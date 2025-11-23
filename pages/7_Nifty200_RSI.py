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
    """Ensure 'Ticker' column exists, uppercase, dedupe, drop empties."""
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
    return tickers

def _fetch_ohlc_for_ticker(ticker_ns: str, days: int = 30):
    """Fetch last N trading days OHLC via yfinance for a '.NS' ticker."""
    end = datetime.today()
    start = end - timedelta(days=days * 2)  # buffer across weekends/holidays
    df = yf.download(ticker_ns, start=start, end=end, progress=False)
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

    # 1) Read tickers from the sheet/tab
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    if tickers_df.empty or "Ticker" not in tickers_df.columns:
        st.error("No tickers found in Nifty_200 tab. Please check the sheet and try again.")
        st.stop()

    tickers = _normalize_tickers(tickers_df)
    if not tickers:
        st.error("Ticker list is empty after normalization. Please verify the Nifty_200 tab.")
        st.stop()

    # 2) Connect to Supabase
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    # 3) Process each ticker with progress and per‑ticker error isolation
    progress = st.progress(0)
    status = st.empty()
    success_count, fail_count = 0, 0
    errors = []

    total = len(tickers)
    for i, t in enumerate(tickers, start=1):
        status.text(f"Processing {t}.NS ({i}/{total})…")
        try:
            records = _fetch_ohlc_for_ticker(f"{t}.NS", days=30)
            if records:
                # Use small batches to keep payloads reasonable
                batch_size = 500
                for j in range(0, len(records), batch_size):
                    _upsert_ohlc_batch(supabase, records[j:j+batch_size])
                success_count += 1
            else:
                fail_count += 1
                errors.append(f"{t}: no OHLC data returned")
        except Exception as e:
            fail_count += 1
            errors.append(f"{t}: {e}")

        progress.progress(i / total)
        time.sleep(0.05)  # gentle pacing

    # 4) Summary
    status.empty()
    progress.empty()

    if errors:
        with st.expander("⚠️ Details for failures"):
            for msg in errors:
                st.write(f"- {msg}")

    st.success(f"✅ Completed OHLC load. Success: {success_count}, Failed: {fail_count}, Total: {total}")

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