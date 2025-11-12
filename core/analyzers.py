import pandas as pd
from datetime import datetime
import time
from core.columns import col
import yfinance as yf
import requests


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
                self.signal_log.append({
                    "Date": datetime.today().date(),
                    "Ticker": row[col("ticker")],
                    "Signal": "BUY",
                    "Price": round(float(row[col("current_price")]), 2)
                })

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
                    self.signal_log.append({
                        "Date": datetime.today().date(),
                        "Ticker": row[col("ticker")],
                        "Signal": "BUY",
                        "Price": round(float(price), 2)
                    })

class TrendingValueAnalyzer:
    def __init__(self, **kwargs):
        self.signal_log = []
        self.analysis_df = pd.DataFrame()

    def _normalize_ticker(self, ticker):
        return ticker.replace("NSE:", "").strip() + ".NS"

    def _fetch_nse_ratios(self, ticker):
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
            session.get("https://www.nseindia.com", headers=headers)
            url = f"https://www.nseindia.com/api/quote-equity?symbol={ticker}"
            response = session.get(url, headers=headers, timeout=5)
            data = response.json()
            meta = data.get("metadata", {})
            return {
                "PE": meta.get("pE"),
                "PB": meta.get("bookValue") and meta.get("lastPrice") / meta.get("bookValue"),
                "EV_EBITDA": pd.NA,
                "P_Sales": pd.NA,
                "P_CashFlow": pd.NA
            }
        except Exception as e:
            print(f"⚠️ NSE fetch failed for {ticker}: {e}")
            return {col: pd.NA for col in ["PE", "PB", "EV_EBITDA", "P_Sales", "P_CashFlow"]}

    def analyze_buy(self, df):
        self.signal_log = []
        self.analysis_df = pd.DataFrame()

        if "Ticker" not in df.columns:
            print("⚠️ 'Ticker' column missing.")
            return

        df["Normalized Ticker"] = df["Ticker"].apply(self._normalize_ticker)
        tickers = df["Normalized Ticker"].dropna().unique().tolist()

        # 📈 Momentum from yFinance
        price_data = yf.download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=False)
        if price_data.empty:
            print("⚠️ Price data download failed.")
            return

        if isinstance(price_data.columns, pd.MultiIndex) and "Adj Close" in price_data.columns.levels[0]:
            adj_close = price_data["Adj Close"]
        elif "Adj Close" in price_data.columns:
            adj_close = price_data["Adj Close"]
        else:
            print("⚠️ 'Adj Close' not found.")
            return

        returns = adj_close.pct_change(fill_method=None).dropna()
        cumulative_returns = (1 + returns).prod() - 1
        momentum_rank = cumulative_returns.rank(ascending=False)

        # 📊 Valuation ratios from NSE
        ratios = {}
        for ticker in df["Normalized Ticker"]:
            nse_ticker = ticker.replace(".NS", "")
            ratios[ticker] = self._fetch_nse_ratios(nse_ticker)
            time.sleep(1.5)  # avoid rate limit

        df_ratios = pd.DataFrame(ratios).T
        df_ratios["Momentum Rank"] = momentum_rank

        # 🧠 Value Composite Score (VCS)
        value_cols = ["PE", "PB", "EV_EBITDA", "P_Sales", "P_CashFlow"]
        for col in value_cols:
            df_ratios[col] = pd.to_numeric(df_ratios[col], errors="coerce")
            df_ratios[f"{col}_Rank"] = df_ratios[col].rank(ascending=True)

        df_ratios["VCS"] = df_ratios[[f"{col}_Rank" for col in value_cols]].mean(axis=1)
        df_ratios["Final Score"] = df_ratios[["VCS", "Momentum Rank"]].mean(axis=1)

        df_final = df_ratios.reset_index().rename(columns={"index": "Ticker"})
        df_final["Signal"] = ""
        df_final.loc[:24, "Signal"] = "BUY"

        self.analysis_df = df_final.copy()
        self.signal_log = df_final[df_final["Signal"] == "BUY"].to_dict("records")

    def analyze_sell(self, df):
        self.signal_log += []  # No SELL logic yet
