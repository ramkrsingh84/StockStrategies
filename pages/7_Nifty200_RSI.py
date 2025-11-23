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


def fetch_ohlc_normalized(ticker, days=90):
    # Try with raw OHLC, avoid adjusted surprises, avoid grouped multi-ticker
    df = yf.download(
        ticker,
        period=f"{days}d",
        interval="1d",
        auto_adjust=False,
        group_by="column"
    )

    if df is None or df.empty:
        return None

    # If MultiIndex columns, try to pick this ticker's slice
    if isinstance(df.columns, pd.MultiIndex):
        # Common pattern: (ticker, field)
        if (ticker,) in [tuple([lvl]) for lvl in df.columns.get_level_values(0)]:
            try:
                df = df.xs(ticker, axis=1, level=0)
            except Exception:
                pass
        # Flatten remaining multiindex to strings
        df.columns = ["_".join([str(x) for x in c if x is not None]) for c in df.columns]
    else:
        # Single level columns; ensure consistent casing
        df.columns = [str(c) for c in df.columns]

    # Reset index to expose date/datetime
    df = df.reset_index()

    # Build a canonical date column 'trade_date'
    date_col = None
    for candidate in ["Date", "Datetime", "date", "datetime"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        # If index got named something odd, use the first column
        date_col = df.columns[0]

    # Normalize column names to lowercase for consistent access
    df.columns = [c.lower() for c in df.columns]

    # Recompute date_col after lowering
    date_col = date_col.lower()

    # Create trade_date in ISO format
    df["trade_date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")

    # Map possible OHLC variants to canonical names
    # After lowercasing, we expect 'open','high','low','close','volume'
    # If they came as 'adj close', we still need raw 'close'; we’ll check availability.
    required_fields = {}
    for field in ["open", "high", "low", "close", "volume"]:
        if field in df.columns:
            required_fields[field] = df[field]
        else:
            # Try common variants from flattened names
            # e.g., 'reliance.ns_open' or 'open_reliance.ns'
            candidates = [c for c in df.columns if c.endswith(f"_{field}") or c.startswith(f"{field}_")]
            if candidates:
                required_fields[field] = df[candidates[0]]
            else:
                # If truly missing (e.g., intraday volume), set None
                required_fields[field] = None

    # Replace NaN with None for Supabase
    df = df.where(pd.notnull(df), None)

    # Final payload DataFrame with canonical columns
    payload = pd.DataFrame({
        "ticker": ticker,
        "trade_date": df["trade_date"],
        "open": required_fields["open"],
        "high": required_fields["high"],
        "low": required_fields["low"],
        "close": required_fields["close"],
        "volume": required_fields["volume"],
    })

    # Drop rows where trade_date is missing
    payload = payload[payload["trade_date"].notnull()]

    # If open/high/low/close are tuples/Series, convert or drop
    for col in ["open", "high", "low", "close", "volume"]:
        if col in payload.columns and isinstance(payload[col], pd.Series):
            # leave as Series; Supabase JSON serialization will convert per-row values
            pass

    return payload




# ✅ Loader function
def load_ohlc_to_supabase(tickers, days=90):
    for t in tickers:
        symbol = t.strip().upper() + ".NS"
        try:
            payload = fetch_ohlc_normalized(symbol, days=90)
            if payload is None or payload.empty:
                st.warning(f"No OHLC data for {symbol}")
                continue

            # Convert DataFrame to list of dicts
            rows = payload.to_dict(orient="records")

            if not rows:
                st.warning(f"No valid rows after normalization for {symbol}")
                continue

            resp = supabase.table("ohlc_data").upsert(rows).execute()
            st.write(f"{symbol} → inserted {len(rows)} rows; error:", getattr(resp, "error", None))

        except Exception as e:
            st.error(f"Error loading {symbol}: {e}")


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