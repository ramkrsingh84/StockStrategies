import pandas as pd
from datetime import datetime
import time
from core.columns import col
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from supabase import create_client
import os
import json


# 🔎 Load holiday JSON once at module level
HOLIDAY_FILE = os.path.join(os.path.dirname(__file__), "..", "pages", "nse_holidays.json")
try:
    with open(HOLIDAY_FILE, "r") as f:
        NSE_HOLIDAYS = json.load(f)
except FileNotFoundError:
    NSE_HOLIDAYS = {}  # fallback if file missing

def filter_trading_days(df: pd.DataFrame) -> pd.DataFrame:
    """Drop weekends and NSE holidays automatically."""
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    # Drop weekends
    df = df[df["trade_date"].dt.dayofweek < 5]
    # Drop NSE holidays
    years = df["trade_date"].dt.year.unique()
    all_holidays = []
    for y in years:
        all_holidays.extend(NSE_HOLIDAYS.get(str(y), []))
    if all_holidays:
        holidays = pd.to_datetime(all_holidays)
        df = df[~df["trade_date"].isin(holidays)]
    return df

class SignalAnalyzer:
    def __init__(self, sell_threshold_pct=12):
        self.signal_log = []
        self.sell_threshold_pct = sell_threshold_pct

    def analyze_buy(self, df):
        df = df.dropna(subset=[col("current_price"), col("dma_100"), col("min_6m"), col("last_close")])

        for _, row in df.iterrows():
            if row[col("current_price")] > row[col("dma_100")] and \
               row[col("current_price")] > row[col("min_6m")] and \
               row[col("last_close")] < row[col("dma_100")]:

                signal = {
                    "Date": datetime.today().date(),
                    "Ticker": row[col("ticker")],
                    "Signal": "BUY",
                    "Price": round(float(row[col("current_price")]), 2)
                }

                # ✅ Add PEG with fallback for #NA, N/A, etc.
                peg_raw = row.get(col("PEG"), None)
                try:
                    peg_val = float(peg_raw)
                    signal["PEG"] = round(peg_val, 2)
                except (ValueError, TypeError):
                    signal["PEG"] = "NA"

                self.signal_log.append(signal)



    def analyze_sell(self, df):
        if df.empty or col("sell_date") not in df.columns:
            return
        df = df[df[col("sell_date")].isna()]

        df = df.copy()
        df["weighted_cost"] = df[col("buy_price")] * df[col("buy_qty")]
        grouped = df.groupby(col("ticker")).agg({
            "weighted_cost": "sum",
            col("buy_qty"): "sum",
            col("current_price"): "first"
        })
        grouped["avg_buy"] = grouped["weighted_cost"] / grouped[col("buy_qty")]
        grouped["pnl_pct"] = ((grouped[col("current_price")] - grouped["avg_buy"]) / grouped["avg_buy"]) * 100

        for ticker, row in grouped.iterrows():
            if row["pnl_pct"] >= self.sell_threshold_pct:
                self.signal_log.append({
                    "Date": datetime.today().date(),
                    "Ticker": ticker,
                    "Signal": "SELL",
                    "Price": round(float(row[col("current_price")]), 2),
                    "P&L %": round(row["pnl_pct"], 2)
                })

class ConsolidateAnalyzer(SignalAnalyzer):
    def analyze_buy(self, df):
        df = df.dropna(subset=[
            col("ticker"), col("current_price"), col("high_52w_date"), col("low_52w_date"),
            col("dma_5"), col("dma_20"), col("dma_50"), col("dma_100"), col("dma_200")
        ])
        for _, row in df.iterrows():
            price = row[col("current_price")]
            dma_vals = [row[col(f"dma_{d}")] for d in [5, 20, 50, 100, 200]]
            high_date = pd.to_datetime(row[col("high_52w_date")], errors="coerce", dayfirst=True)
            low_date = pd.to_datetime(row[col("low_52w_date")], errors="coerce", dayfirst=True)

            if pd.notna(high_date) and pd.notna(low_date) and high_date < low_date:
                if all(0.95 * price < val < 1.05 * price for val in dma_vals):
                    signal={
                        "Date": datetime.today().date(),
                        "Ticker": row[col("ticker")],
                        "Signal": "BUY",
                        "Price": round(float(price), 2)
                    }
                    # ✅ Add PEG with fallback for #NA, N/A, etc.
                    peg_raw = row.get(col("PEG"), None)
                    try:
                        peg_val = float(peg_raw)
                        signal["PEG"] = round(peg_val, 2)
                    except (ValueError, TypeError):
                        signal["PEG"] = "NA"

                    self.signal_log.append(signal)

class TrendingValueAnalyzer:
    def __init__(self, **kwargs):
        self.signal_log = []
        self.analysis_df = pd.DataFrame()

    def analyze_buy(self, df):
        # Store the sheet-driven buy table
        self.analysis_df = df.copy()
        self.signal_log = []  # No BUY logic needed

    def analyze_sell(self, df):
        self.signal_log += []  # No SELL logic needed

    def get_sheet_summary(self):
        if self.analysis_df.empty or "Ticker" not in self.analysis_df.columns:
            return pd.DataFrame()

        df = self.analysis_df.copy()
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        df.rename(columns={
            "ticker": "Ticker",
            "current price": "Price",
            "final rank": "Final Rank"
        }, inplace=True)

        # Coerce price to numeric and drop missing
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df = df.dropna(subset=["Price"])
        return df[["Ticker", "Price", "Final Rank"]].copy()

class GARPAnalyzer:
    def __init__(self, **kwargs):
        self.signal_log = []
        self.analysis_df = pd.DataFrame()

    def analyze_buy(self, df):
        self.analysis_df = df.copy()
        self.signal_log = []  # No BUY logic needed

    def analyze_sell(self, df):
        self.signal_log += []  # No SELL logic yet

    def get_sheet_summary(self):
        if self.analysis_df.empty or "Ticker" not in self.analysis_df.columns:
            return pd.DataFrame()

        df = self.analysis_df.copy()

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        df.rename(columns={
            "ticker": "Ticker",
            "current price": "Price",
            "final rank": "Final Rank"
        }, inplace=True)

        # Coerce price to numeric and drop missing
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df = df.dropna(subset=["Price"])

        return df[["Ticker", "Price", "Final Rank"]].copy()



class Nifty200RSIAnalyzer:
    def __init__(self, sell_threshold_pct=12, **kwargs):
        self.sell_threshold_pct = sell_threshold_pct
        self.signal_log = []
        self.analysis_df = pd.DataFrame()
        self.active_signals = {}
        # Supabase client created only here, not in runner
        import streamlit as st
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        self.supabase = create_client(url, key)

    def _detect_ticker_column(self, df: pd.DataFrame) -> str:
        for c in ["Ticker","ticker","Symbol","symbol","Instrument","instrument"]:
            if c in df.columns:
                return c
        for c in df.columns:
            if str(c).lower().startswith("tick") or str(c).lower().startswith("symb"):
                return c
        raise KeyError("No ticker column found in buy_df")

    def _fetch_ohlc_for_tickers(self, tickers: list, days: int = 90) -> pd.DataFrame:
        from datetime import timedelta
        cutoff = (datetime.today() - timedelta(days=days)).date().isoformat()
        frames = []
        CHUNK = 100
        for i in range(0, len(tickers), CHUNK):
            batch = tickers[i:i+CHUNK]
            resp = (
                self.supabase.table("ohlc_data")
                .select("*")
                .in_("ticker", batch)
                .gte("trade_date", cutoff)
                .execute()
            )
            data = getattr(resp, "data", [])
            if data:
                frames.append(pd.DataFrame(data))
        if not frames:
            return pd.DataFrame(columns=["ticker","trade_date","open","high","low","close","volume"])
        df = pd.concat(frames, ignore_index=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    def compute_rsi_wilder(self, series: pd.Series, period: int = 14) -> pd.Series:
        """Compute RSI using Wilder's smoothing method."""
        if series is None or series.empty or series.shape[0] < period + 1:
            return pd.Series([None] * series.shape[0], index=series.index)

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


    def identify_buy_signals(self, df: pd.DataFrame) -> list:
        """Identify BUY signals based on RSI cycle rules."""
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

        return buy_points
        
    # -------------------------------
    # PEG Ratio Functions
    # -------------------------------
    def fetch_peg_ratio(self, ticker: str):
        """
        Fetch PEG ratio using yFinance.
        PEG = PE / Earnings Growth
        Returns None if data unavailable.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            pe = info.get("trailingPE")
            growth = info.get("earningsGrowth")

            if pe is None or growth is None or growth == 0:
                return None

            return round(pe / growth, 2)
        except Exception:
            return None


    def highlight_peg(self, val):
        """Style function for DataFrame: green if PEG < 1.5."""
        try:
            if val is not None and float(val) < 1.5:
                return "color: green"
        except:
            pass
        return ""

    def analyze_buy(self, buy_df: pd.DataFrame):
        if buy_df is None or buy_df.empty:
            self.analysis_df = pd.DataFrame(columns=["Ticker","RSI","Signal","PEG","Status","Last date"])
            return

        ticker_col = self._detect_ticker_column(buy_df)
        raw_tickers = buy_df[ticker_col].astype(str).str.strip().dropna().unique().tolist()

        normalized = []
        for t in raw_tickers:
            tt = t.upper()
            if tt.startswith("NSE:"):
                tt = tt.split("NSE:")[1] + ".NS"
            elif not tt.endswith(".NS"):
                tt = tt + ".NS"
            normalized.append(tt)

        ohlc = self._fetch_ohlc_for_tickers(normalized, days=90)
        if ohlc.empty:
            self.analysis_df = pd.DataFrame(columns=["Ticker","RSI","Signal","Status","Last date"])
            return

        # 🔎 Filter trading days automatically
        ohlc = filter_trading_days(ohlc)

        results = []
        for ticker in sorted(ohlc["ticker"].dropna().unique()):
            sub = ohlc[ohlc["ticker"] == ticker].dropna(subset=["trade_date","close"]).sort_values("trade_date")
            sub["rsi"] = self.compute_rsi_wilder(sub["close"], period=14)
            buy_points = self.identify_buy_signals(sub)

            recent = sub.tail(30)

            if recent.empty or recent["rsi"].isna().all():
                continue

            latest_rsi = recent["rsi"].iloc[-1]
            status = "Active" if self.active_signals.get(ticker, False) else "Inactive"

            # --- Clear condition ---
            if latest_rsi >= 55:
                self.active_signals[ticker] = False
                status = "Inactive"

            # --- Trigger condition ---
            dipped_points = recent[recent["rsi"] <= 35]
            if not dipped_points.empty:
                dip_index = dipped_points.index[-1]  # last dip
                after_dip = recent.loc[dip_index:]

                crossed_40 = (after_dip["rsi"] >= 40).any()
                blocked = (after_dip["rsi"] >= 55).any()

                if crossed_40 and not blocked:
                    if not self.active_signals.get(ticker, False):
                        self.active_signals[ticker] = True
                        status = "Active"

            # ✅ Append PEG here
            peg_val = self.fetch_peg_ratio(ticker)
            
            results.append({
                "Ticker": ticker,
                "RSI": round(latest_rsi, 2) if pd.notna(latest_rsi) else None,
                "PEG": peg_val,
                "Signal": "BUY" if self.active_signals.get(ticker, False) else "",
                "Status": status,
                "Last date": recent["trade_date"].iloc[-1].date().isoformat()
            })

        self.analysis_df = pd.DataFrame(results)
        self.signal_log.extend(results)

    def analyze_sell(self, portfolio_df: pd.DataFrame):
        pass

    def get_sheet_summary(self) -> pd.DataFrame:
        if self.analysis_df.empty:
            return pd.DataFrame(columns=["Ticker","RSI","PEG","Signal","Status","Last date"])
        # Apply formatting and highlight PEG < 1.5
        return self.analysis_df.copy().sort_values(["Status","Ticker"], ascending=[False,True])

class EarningsGapAnalyzer:
    def __init__(self, **kwargs):
        self.signal_log = []
        self.analysis_df = pd.DataFrame()

    # --- Helper to detect ticker column ---
    def _detect_ticker_column(self, df: pd.DataFrame) -> str:
        for c in ["Ticker","ticker","Symbol","symbol","Instrument","instrument"]:
            if c in df.columns:
                return c
        for c in df.columns:
            lc = str(c).lower()
            if lc.startswith("tick") or lc.startswith("symb"):
                return c
        raise KeyError("No ticker column found in DataFrame")

    # --- RSI helper ---
    def compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.bfill().ffill()

    # --- PEG highlight ---
    def highlight_peg(self, val):
        try:
            if val is not None and float(val) < 1.5:
                return "color: green"
        except:
            pass
        return ""

    def analyze_buy(self, df: pd.DataFrame):
        if df is None or df.empty:
            self.analysis_df = pd.DataFrame(columns=[
                "Ticker","RSI","PEG","Signal","Entry Date","Exit Date","Status","Reason"
            ])
            return

        df = df.copy()
        ticker_col = self._detect_ticker_column(df)

        # Compute RSI if missing
        if "rsi14" not in df.columns and "Close" in df.columns:
            df["rsi14"] = df.groupby(ticker_col, group_keys=False)["Close"].apply(lambda s: self.compute_rsi(s, 14))

        # Rolling metrics
        if "Volume" in df.columns and "Close" in df.columns:
            df["avg_vol_20"] = df.groupby(ticker_col, group_keys=False)["Volume"].rolling(20).mean().reset_index(level=0, drop=True)
            df["ret_20"] = df.groupby(ticker_col, group_keys=False)["Close"].pct_change(20)

        results = []
        for idx, row in df.iterrows():
            # Gap condition
            if idx == 0 or row["Open"] < 1.02 * df.loc[idx-1, "Close"]:
                continue
            # Liquidity + PEG filters
            if row.get("avg_vol_20", 0) < 1_000_000:
                continue
            if row.get("peg_ratio", None) is None or row["peg_ratio"] >= 4.5:
                continue

            gap_low = min(row["Open"], row["Low"])
            i3 = idx + 2
            if i3 >= len(df): 
                continue
            r3 = df.iloc[i3]

            vol_ok = r3["Volume"] >= 1.2 * r3["avg_vol_20"]
            price_ok = r3["Close"] > gap_low
            momentum_ok = (r3["rsi14"] >= 40) and (r3["ret_20"] >= 0)

            if not (vol_ok and price_ok and momentum_ok):
                continue

            # BUY signal
            results.append({
                "Ticker": row[ticker_col],
                "RSI": round(r3["rsi14"], 2),
                "PEG": row["peg_ratio"],
                "Signal": "BUY",
                "Entry Date": r3["Date"],
                "Exit Date": None,
                "Status": "Active",
                "Reason": "Earnings Gap Continuation"
            })

        self.analysis_df = pd.DataFrame(results)
        self.signal_log.extend(results)

    def analyze_sell(self, portfolio_df: pd.DataFrame):
        # Optional: implement exit logic later
        pass

    def get_sheet_summary(self) -> pd.DataFrame:
        if self.analysis_df.empty:
            return pd.DataFrame(columns=[
                "Ticker","RSI","PEG","Signal","Entry Date","Exit Date","Status","Reason"
            ])
        return self.analysis_df.copy().sort_values(["Status","Ticker"], ascending=[False,True])
