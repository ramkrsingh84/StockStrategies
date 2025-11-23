import json
import pandas as pd
import yfinance as yf
import streamlit as st
from supabase import create_client
from core.fetcher import DataFetcher
from core.runner import StrategyRunner
from config import STRATEGY_CONFIG
from datetime import datetime, timedelta
import plotly.graph_objects as go
from core.analyzers import filter_trading_days
import requests
import zipfile
import io
import os


# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Nifty200 RSI Strategy", layout="wide")
st.title("📈 Nifty200 RSI Strategy Analysis")

# -------------------------------
# OHLC Pruning
# -------------------------------
def prune_ohlc_data():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    cutoff_date = (datetime.today() - timedelta(days=730)).date().isoformat()
    supabase.table("ohlc_data").delete().lt("trade_date", cutoff_date).execute()

    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    if tickers_df.empty or "Ticker" not in tickers_df.columns:
        st.error("No tickers found in Nifty_200 tab.")
        return

    tickers = tickers_df["Ticker"].dropna().tolist()
    normalized = []
    for t in tickers:
        symbol = t.strip().upper()
        if symbol.startswith("NSE:"):
            symbol = symbol.split("NSE:")[1] + ".NS"
        else:
            symbol = symbol + ".NS"
        normalized.append(symbol)

    supabase.table("ohlc_data").delete().not_.in_("ticker", normalized).execute()
    st.success(f"✅ Pruned OHLC data: kept last 2 years and only {len(normalized)} Nifty_200 tickers")

# -------------------------------
# Load holiday JSON
# -------------------------------
# 🔎 Load holiday JSON once at module level
HOLIDAY_FILE = os.path.join(os.path.dirname(__file__), "..", "pages", "nse_holidays.json")
try:
    with open(HOLIDAY_FILE, "r") as f:
        HOLIDAYS = json.load(f)
except FileNotFoundError:
    HOLIDAYS = {}  # fallback if file missing

def is_holiday(date: datetime) -> bool:
    year = str(date.year)
    return date.strftime("%Y-%m-%d") in HOLIDAYS.get(year, [])

# -------------------------------
# Fetch Bhavcopy
# -------------------------------
def fetch_bhavcopy(date: datetime):
    day = date.strftime("%d")
    month = date.strftime("%b").upper()
    year = date.strftime("%Y")
    date_str = f"{day}{month}{year}"

    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nseindia.com/"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_file = z.namelist()[0]
            df = pd.read_csv(z.open(csv_file))

        df = df[df["SERIES"] == "EQ"]

        payload = pd.DataFrame({
            "ticker": "NSE:" + df["SYMBOL"].astype(str),
            "trade_date": pd.to_datetime(df["TIMESTAMP"]).dt.strftime("%Y-%m-%d"),
            "open": pd.to_numeric(df["OPEN"], errors="coerce"),
            "high": pd.to_numeric(df["HIGH"], errors="coerce"),
            "low": pd.to_numeric(df["LOW"], errors="coerce"),
            "close": pd.to_numeric(df["CLOSE"], errors="coerce"),
            "volume": pd.to_numeric(df["TOTTRDQTY"], errors="coerce"),
        })
        return payload
    except Exception as e:
        print(f"❌ Error fetching bhavcopy {date_str}: {e}")
        return None


def load_bhavcopy_last_two_years(tickers):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    progress = st.progress(0)
    status = st.empty()
    success_count, fail_count = 0, 0

    start_date = datetime.today() - timedelta(days=730)
    end_date = datetime.today()
    total_days = (end_date - start_date).days

    for i in range(total_days):
        date = end_date - timedelta(days=i)

        # Skip weekends and holidays
        if date.weekday() >= 5 or is_holiday(date):
            continue

        payload = fetch_bhavcopy(date)
        if payload is None or payload.empty:
            fail_count += 1
            continue

        payload = payload[payload["ticker"].isin(tickers)]
        if payload.empty:
            continue

        rows = payload.to_dict(orient="records")
        supabase.table("ohlc_data").upsert(rows).execute()
        success_count += len(rows)

        status.text(f"Inserted {len(rows)} rows for {date.strftime('%Y-%m-%d')}")
        progress.progress((i+1)/total_days)

    status.empty()
    progress.empty()
    st.success(f"📥 Completed 2-year bhavcopy load. Success rows: {success_count}, Failed days: {fail_count}")



# -------------------------------
# OHLC Fetch + Normalize
# -------------------------------

def fetch_ohlc_normalized_nse(raw_symbol: str, days: int = 180):
    """
    Fetch OHLC data from NSE for the given raw symbol (e.g. 'ADANIENT').
    """

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    }

    # 🔑 Step 1: establish cookies
    session.get("https://www.nseindia.com", headers=headers, timeout=10)

    # 🔑 Step 2: build URL
    end_date = datetime.today().strftime("%d-%m-%Y")
    start_date = (datetime.today() - timedelta(days=days*2)).strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={raw_symbol}&series=EQ&from={start_date}&to={end_date}"

    # 🔑 Step 3: call API with cookies + headers
    resp = session.get(url, headers=headers, timeout=15)

    # Debug logging
    st.write(f"Status → {resp.status_code}")
    st.write(f"Text sample → {resp.text[:300]}")

    if resp.status_code != 200:
        st.error(f"NSE API error for {raw_symbol}: {resp.status_code}")
        return None

    try:
        data = resp.json().get("data", [])
    except Exception as e:
        st.error(f"❌ JSON parse failed for {raw_symbol}: {e}")
        return None

    if not data:
        st.warning(f"⚠️ No OHLC data returned for {raw_symbol}")
        return None

    df = pd.DataFrame(data)
    df["trade_date"] = pd.to_datetime(df["CH_TIMESTAMP"]).dt.strftime("%Y-%m-%d")

    payload = pd.DataFrame({
        "trade_date": df["trade_date"],
        "open": pd.to_numeric(df["CH_OPENING_PRICE"], errors="coerce"),
        "high": pd.to_numeric(df["CH_TRADE_HIGH_PRICE"], errors="coerce"),
        "low": pd.to_numeric(df["CH_TRADE_LOW_PRICE"], errors="coerce"),
        "close": pd.to_numeric(df["CH_CLOSING_PRICE"], errors="coerce"),
        "volume": pd.to_numeric(df["CH_TOT_TRADED_QTY"], errors="coerce"),
    })
    return payload.dropna(subset=["trade_date","close"])





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

    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=0)
        except Exception:
            pass
        df.columns = ["_".join([str(x) for x in c if x is not None]) for c in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    df = df.reset_index()
    date_col = next((c for c in ["Date","Datetime","date","datetime"] if c in df.columns), df.columns[0])
    df.columns = [c.lower() for c in df.columns]
    date_col = date_col.lower()
    df["trade_date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")

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
def load_ohlc_to_supabase(tickers, days=180):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    progress = st.progress(0)
    status = st.empty()
    success_count, fail_count = 0, 0
    total = len(tickers)

    for i, t in enumerate(tickers, start=1):
        symbol = t.strip().upper()
        if symbol.startswith("NSE:"):
            raw_symbol = symbol.split("NSE:")[1]
        else:
            raw_symbol = symbol

        st.write(f"🔍 Raw symbol for {symbol} → {raw_symbol}")
        status.text(f"Processing {symbol} ({i}/{total})…")
        try:
            payload = fetch_ohlc_normalized_nse(raw_symbol, days=days)

            if payload is None or payload.empty:
                st.error(f"❌ Skipping {symbol}: no OHLC data returned from NSE")
                fail_count += 1
                continue

            payload["ticker"] = symbol  # store as NSE:TICKER
            rows = payload.to_dict(orient="records")

            resp = supabase.table("ohlc_data").upsert(rows).execute()
            st.write(f"✅ {symbol} → inserted {len(rows)} rows; error:", getattr(resp, "error", None))
            success_count += 1

        except Exception as e:
            st.error(f"❌ Error loading {symbol}: {e}")
            fail_count += 1
            continue  # ✅ skip and move on

        progress.progress(i / total)


    status.empty()
    progress.empty()
    st.success(f"📥 Completed OHLC load. Success: {success_count}, Failed: {fail_count}, Total: {total}")




# -------------------------------
# Chart with RSI & Signals
# -------------------------------
def compute_rsi_wilder(series: pd.Series, period=14) -> pd.Series:
    """Compute RSI using Wilder's smoothing (matches Upstox)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.iloc[1:period+1].mean()
    avg_loss = loss.iloc[1:period+1].mean()

    rsi_values = [None] * len(series)

    for i in range(period+1, len(series)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period

        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        rsi_values[i] = rsi

    return pd.Series(rsi_values, index=series.index)


def plot_ticker_chart(ticker: str, days: int = 180):
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase = create_client(url, key)

    cutoff = (datetime.today() - timedelta(days=days)).date().isoformat()
    resp = (
        supabase.table("ohlc_data")
        .select("*")
        .eq("ticker", ticker)
        .gte("trade_date", cutoff)
        .order("trade_date")
        .execute()
    )
    data = getattr(resp, "data", [])
    if not data:
        st.warning(f"No OHLC data found for {ticker}")
        return

    df = pd.DataFrame(data)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # 🔎 Filter trading days
    df = filter_trading_days(df)

    # Compute Wilder RSI
    df["rsi"] = compute_rsi_wilder(df["close"], period=14)

    # --- Identify BUY signals ---
    buy_points = []
    dipped = False
    for i in range(1, len(df)):
        rsi_prev, rsi_now = df["rsi"].iloc[i-1], df["rsi"].iloc[i]
        if pd.isna(rsi_prev) or pd.isna(rsi_now):
            continue

        if rsi_now <= 35:
            dipped = True
        if rsi_now >= 55:
            dipped = False
        if dipped and rsi_prev < 40 and rsi_now >= 40:
            buy_points.append((df["trade_date"].iloc[i], rsi_now))

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df["trade_date"],
        open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="OHLC"
    ))

    # Wilder RSI line
    fig.add_trace(go.Scatter(
        x=df["trade_date"], y=df["rsi"],
        line=dict(color="blue"), name="RSI (Wilder)",
        yaxis="y2"
    ))

    # BUY markers
    if buy_points:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in buy_points],
            y=[p[1] for p in buy_points],
            mode="markers",
            marker=dict(color="green", size=10, symbol="triangle-up"),
            name="BUY Signal", yaxis="y2"
        ))

    fig.update_layout(
        title=f"{ticker} Price & Wilder RSI BUY Signals",
        xaxis=dict(domain=[0, 1]),
        yaxis=dict(title="Price"),
        yaxis2=dict(title="RSI", overlaying="y", side="right", range=[0,100]),
        height=600
    )

    st.plotly_chart(fig, width="stretch")


# -------------------------------
# Buttons
# -------------------------------
if st.button("📥 Load OHLC Data"):
    # 1. Get tickers from Google Sheet (Nifty_200 tab)
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    if tickers_df.empty or "Ticker" not in tickers_df.columns:
        st.error("No tickers found in Nifty_200 tab.")
        st.stop()

    tickers = tickers_df["Ticker"].dropna().tolist()
    tickers = [t.strip().upper() for t in tickers]

    # 2. Load bhavcopy data into Supabase, but filter only for Nifty_200 tickers
    load_bhavcopy_last_two_years(tickers)


if st.button("▶️ Run Strategy"):
    runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
    runner.run()
    summary_df = runner.analyzer.get_sheet_summary()

    if not summary_df.empty:
        st.subheader("📋 Nifty200 RSI Summary")
        summary_df["RSI"] = pd.to_numeric(summary_df["RSI"], errors="coerce")

        st.dataframe(
            summary_df[["Ticker", "RSI", "Signal", "Status", "Last date"]]
                .sort_values(["Status", "Ticker"], ascending=[False, True])
                .style.format({"RSI": "{:.2f}"}),
            width="stretch"
        )

if st.button("🧹 Prune OHLC Data"):
    prune_ohlc_data()

# -------------------------------
# Interactive Chart Section
# -------------------------------
st.markdown("---")
st.subheader("📊 Chart Active Tickers")

runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
runner.run()
summary_df = runner.analyzer.get_sheet_summary()

active_tickers = summary_df[summary_df["Status"] == "Active"]["Ticker"].dropna().tolist()

if active_tickers:
    selected_ticker = st.selectbox("Select Active Ticker", active_tickers)
    if selected_ticker:
        # Normalize to Supabase format
        symbol = selected_ticker.strip().upper()
        if symbol.startswith("NSE:"):
            symbol = symbol.split("NSE:")[1] + ".NS"
        elif not symbol.endswith(".NS"):
            symbol = symbol + ".NS"

        plot_ticker_chart(symbol, days=180)
else:
    st.info("No Active tickers at the moment.")



with st.container():
    st.markdown("---")
    st.page_link("main.py", label="⬅️ Back to Home", icon="🏠")