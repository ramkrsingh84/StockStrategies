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


# 🔒 Auth check
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.warning("🔒 Please login from the Home page to access this section.")
    st.stop()

st.set_page_config(page_title="Nifty200 RSI Strategy", layout="wide")
st.title("📈 Nifty200 RSI Strategy Analysis")

# -------------------------------
# PEG calculation
# -------------------------------

def fetch_peg_ratio(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        pe = info.get("trailingPE")
        growth = info.get("earningsGrowth")

        if pe is None or growth is None or growth == 0:
            return None

        peg = pe / growth
        return round(peg, 2)
    except Exception as e:
        st.warning(f"PEG ratio not available for {ticker}: {e}")
        return None




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
# OHLC Fetch + Normalize
# -------------------------------
def fetch_ohlc_normalized(ticker: str, days: int = 180):
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

            # 1. Get existing trade_date values for this ticker
            existing = (
                supabase.table("ohlc_data")
                .select("trade_date")
                .eq("ticker", symbol)
                .execute()
            )

            existing_dates = {row["trade_date"] for row in getattr(existing, "data", [])}

            # 2. Filter out rows that already exist
            new_rows = [r for r in rows if r["trade_date"] not in existing_dates]

            # 3. Insert only new rows
            if new_rows:
                resp = supabase.table("ohlc_data").insert(new_rows).execute()
                st.write(f"{symbol} → inserted {len(new_rows)} new rows; error:", getattr(resp, "error", None))
            else:
                st.write(f"{symbol} → no new rows to insert")
            success_count += 1

        except Exception as e:
            st.error(f"Error loading {symbol}: {e}")
            fail_count += 1

        progress.progress(i / total)

    status.empty()
    progress.empty()
    st.success(f"✅ Completed OHLC load. Success: {success_count}, Failed: {fail_count}, Total: {total}")


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
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    fetcher = DataFetcher("DMA_Data", creds_dict)
    tickers_df = fetcher.fetch("Nifty_200")

    if tickers_df.empty or "Ticker" not in tickers_df.columns:
        st.error("No tickers found in Nifty_200 tab.")
        st.stop()

    tickers = tickers_df["Ticker"].dropna().tolist()
    load_ohlc_to_supabase(tickers, days=180)

if st.button("▶️ Run Strategy"):
    runner = StrategyRunner("Nifty200_RSI", STRATEGY_CONFIG["Nifty200_RSI"])
    runner.run()
    summary_df = runner.analyzer.get_sheet_summary()

    if not summary_df.empty:
        st.subheader("📋 Nifty200 RSI Summary")
        summary_df["RSI"] = pd.to_numeric(summary_df["RSI"], errors="coerce")
        
        # Add PEG ratio column
        pegs = []
        for t in summary_df["Ticker"]:
            # Normalize ticker to Yahoo format
            symbol = t.strip().upper()
            if symbol.startswith("NSE:"):
                symbol = symbol.split("NSE:")[1] + ".NS"
            elif not symbol.endswith(".NS"):
                symbol = symbol + ".NS"

            pegs.append(fetch_peg_ratio(symbol))

        summary_df["PEG"] = pegs
        
        # Conditional formatting: green if PEG < 1.5
        def highlight_peg(val):
            try:
                if val is not None and float(val) < 1.5:
                    return "color: green"
            except:
                pass
            return ""

        st.dataframe(
            summary_df[["Ticker", "RSI", "PEG", "Signal", "Status", "Last date"]]
                .sort_values(["Status", "Ticker"], ascending=[False, True])
                .style.format({"RSI": "{:.2f}", "PEG": "{:.2f}"})
                .applymap(highlight_peg, subset=["PEG"]),,
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