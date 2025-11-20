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
        df["Normalized Ticker"] = df["Ticker"].astype(str).str.upper().str.replace("NSE:", "").str.strip() + ".NS"
        tickers = df["Normalized Ticker"].dropna().unique().tolist()

        price_data = yf.download(tickers, period="1d", interval="1d", progress=False, auto_adjust=False, threads=True)
        if isinstance(price_data.columns, pd.MultiIndex) and "Adj Close" in price_data.columns.levels[0]:
            prices = price_data["Adj Close"].iloc[-1]
        elif "Adj Close" in price_data.columns:
            prices = price_data["Adj Close"].iloc[-1]
        else:
            prices = pd.Series(index=tickers, data=pd.NA)

        df["Price"] = df["Normalized Ticker"].map(prices)
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
        df["Normalized Ticker"] = df["Ticker"].astype(str).str.upper().str.replace("NSE:", "").str.strip() + ".NS"
        tickers = df["Normalized Ticker"].dropna().unique().tolist()

        price_data = yf.download(tickers, period="1d", interval="1d", progress=False, auto_adjust=False, threads=True)
        if isinstance(price_data.columns, pd.MultiIndex) and "Adj Close" in price_data.columns.levels[0]:
            prices = price_data["Adj Close"].iloc[-1]
        elif "Adj Close" in price_data.columns:
            prices = price_data["Adj Close"].iloc[-1]
        else:
            prices = pd.Series(index=tickers, data=pd.NA)
        
        # ✅ Print tickers with missing price
        missing_price_tickers = df.loc[df["Price"].isna(), "Ticker"].tolist()
        if missing_price_tickers:
            print("⚠️ Price not available for:", ", ".join(missing_price_tickers))


        df["Price"] = df["Normalized Ticker"].map(prices)
        return df[["Ticker", "Price", "Final Rank"]].copy()

