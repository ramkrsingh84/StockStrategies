import pandas as pd
from datetime import datetime
import time
from core.columns import col
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor



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
    def __init__(self, supabase_client=None, **kwargs):
        self.supabase = supabase_client
        self.signal_log = []
        self.analysis_df = pd.DataFrame()
        self.active_signals = {}

    def compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        # Guard: empty or too short series
        if series is None or series.empty or series.shape[0] < period + 1:
            return pd.Series([None] * series.shape[0], index=series.index)
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def analyze_buy(self, df: pd.DataFrame):
        results = []

        # 1) Normalize column names to lowercase
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # 2) Ensure we have a ticker column
        # Accept 'ticker' or 'symbol' or 'instrument'
        ticker_col = None
        for c in ["ticker", "symbol", "instrument"]:
            if c in df.columns:
                ticker_col = c
                break
        if ticker_col is None:
            # Try to detect a likely ticker column
            possible = [c for c in df.columns if c.startswith("tick") or c.startswith("symb")]
            if possible:
                ticker_col = possible[0]
            else:
                # hard fail with a clear message
                raise KeyError("No ticker column found. Expected one of: ticker/symbol/instrument.")

        # 3) Ensure trade_date exists, derive from common candidates
        date_col = None
        for c in ["trade_date", "date", "datetime", "timestamp"]:
            if c in df.columns:
                date_col = c
                break
        if date_col is None:
            # If first column looks like a date, use it
            first = df.columns[0]
            if pd.api.types.is_datetime64_any_dtype(df[first]) or "date" in first or "time" in first:
                date_col = first
            else:
                raise KeyError("No date column found. Expected one of: trade_date/date/datetime/timestamp.")

        # Create canonical trade_date string (YYYY-MM-DD)
        df["trade_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

        # 4) Ensure close exists (for RSI)
        close_col = None
        for c in ["close", "adjclose", "adj_close"]:
            if c in df.columns:
                close_col = c
                break
        if close_col is None:
            # Try flattened multiindex names like 'acc.ns_close'
            candidates = [c for c in df.columns if c.endswith("_close") or c.startswith("close_")]
            if candidates:
                close_col = candidates[0]
            else:
                raise KeyError("No close column found. Expected one of: close/adjclose/adj_close or *_close.")

        # 5) Compute per-ticker signals
        for ticker in df[ticker_col].dropna().unique():
            sub = (
                df[df[ticker_col] == ticker]
                .dropna(subset=["trade_date"])
                .sort_values("trade_date")
            )

            # Guard: missing or non-numeric close
            sub[close_col] = pd.to_numeric(sub[close_col], errors="coerce")
            if sub[close_col].isna().all():
                continue

            sub["rsi"] = self.compute_rsi(sub[close_col])

            # Lookback window: last 30 trading rows
            recent = sub.tail(30)
            if recent.empty or recent["rsi"].isna().all():
                # Not enough data to compute RSI
                results.append({
                    "Ticker": ticker,
                    "RSI": None,
                    "Signal": "",
                    "Status": "Inactive",
                    "Last date": sub["trade_date"].iloc[-1] if not sub.empty else None
                })
                continue

            latest_rsi = recent["rsi"].iloc[-1]
            dipped_35 = (recent["rsi"] <= 35).any()
            crossed_40_now = latest_rsi is not None and latest_rsi >= 40
            crossed_50_now = latest_rsi is not None and latest_rsi >= 50

            # Determine current status
            status = "Active" if self.active_signals.get(ticker, False) else "Inactive"

            # Clear signal if crossing 50
            if crossed_50_now:
                self.active_signals[ticker] = False
                status = "Inactive"

            # Trigger buy only if dipped ≤35 within window and now crosses ≥40, and not cleared by ≥50
            if dipped_35 and crossed_40_now and not crossed_50_now:
                if not self.active_signals.get(ticker, False):
                    self.active_signals[ticker] = True
                    status = "Active"

            # Add summary row
            results.append({
                "Ticker": ticker,
                "RSI": round(latest_rsi, 2) if latest_rsi is not None else None,
                "Signal": "BUY" if self.active_signals.get(ticker, False) else "",
                "Status": "Active" if self.active_signals.get(ticker, False) else "Inactive",
                "Last date": recent["trade_date"].iloc[-1] if not recent.empty else None
            })

        self.analysis_df = pd.DataFrame(results)
        self.signal_log.extend(results)

    def get_sheet_summary(self) -> pd.DataFrame:
        return self.analysis_df


