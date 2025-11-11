import pandas as pd
from datetime import datetime
from core.columns import col
import yfinance as yf


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

class MomentumValueAnalyzer:
    def __init__(self, **kwargs):
        self.signal_log = []
    
    def normalize_ticker(ticker):
        return ticker.replace("NSE:", "").strip() + ".NS"

    def analyze_buy(self, df):
        tickers = df["Ticker"].dropna().unique().tolist()
        tickers = [normalize_ticker(t) for t in tickers]

        # 📈 Momentum: 6-month return
        price_data = yf.download(tickers, period="6mo", interval="1d", progress=False)["Adj Close"]
        returns = price_data.pct_change().dropna()
        cumulative_returns = (1 + returns).prod() - 1
        momentum_rank = cumulative_returns.rank(ascending=False)

        # 📊 Value: PE and ROE
        fundamentals = {}
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info
                pe = info.get("trailingPE", None)
                roe = info.get("returnOnEquity", None)
                fundamentals[ticker] = {"PE": pe, "ROE": roe}
            except Exception:
                fundamentals[ticker] = {"PE": None, "ROE": None}

        fundamentals_df = pd.DataFrame(fundamentals).T
        fundamentals_df["Momentum Rank"] = momentum_rank
        fundamentals_df["PE Rank"] = fundamentals_df["PE"].rank(ascending=True)
        fundamentals_df["ROE Rank"] = fundamentals_df["ROE"].rank(ascending=False)
        fundamentals_df["Combined Score"] = fundamentals_df[["Momentum Rank", "PE Rank", "ROE Rank"]].mean(axis=1)

        # ✅ Select top picks
        top_df = fundamentals_df.sort_values("Combined Score").head(10).reset_index().rename(columns={"index": "Ticker"})
        top_df["Signal"] = "BUY"
        self.signal_log = top_df.to_dict("records")
