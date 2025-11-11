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
        self.analysis_df = pd.DataFrame()

    def _normalize_ticker(self, ticker):
        return ticker.replace("NSE:", "").strip() + ".NS"
        
    def download_in_batches(self, tickers, **kwargs):
        all_data = []
        for i in range(0, len(tickers), 25):
            batch = tickers[i:i+25]
            try:
                data = yf.download(batch, **kwargs)
                all_data.append(data)
            except Exception as e:
                print(f"Batch failed: {batch} → {e}")
        return pd.concat(all_data, axis=1) if all_data else pd.DataFrame()

    def analyze_buy(self, df):
    if "Ticker" not in df.columns or "PE" not in df.columns:
        print("⚠️ Required columns missing in buy_df:", df.columns.tolist())
        self.signal_log = []
        self.analysis_df = pd.DataFrame()
        return

    # 🧼 Clean PE column
    df["PE"] = pd.to_numeric(df["PE"], errors="coerce")  # converts #NA or text to NaN

    # ✅ Normalize tickers for yFinance
    tickers = [self._normalize_ticker(t) for t in df["Ticker"].dropna().unique()]
    tickers = [t for t in tickers if isinstance(t, str) and len(t.strip()) > 0]

    # 📈 Momentum: 6-month return
    raw_data = yf.download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=False)
    if raw_data.empty:
        self.signal_log = []
        self.analysis_df = pd.DataFrame()
        return

    if isinstance(raw_data.columns, pd.MultiIndex) and "Adj Close" in raw_data.columns.levels[0]:
        price_data = raw_data["Adj Close"]
    elif "Adj Close" in raw_data.columns:
        price_data = raw_data["Adj Close"]
    else:
        self.signal_log = []
        self.analysis_df = pd.DataFrame()
        return

    returns = price_data.pct_change(fill_method=None).dropna()
    cumulative_returns = (1 + returns).prod() - 1
    momentum_rank = cumulative_returns.rank(ascending=False)

    # 📊 Use PE from sheet, skip ROE
    pe_map = df.set_index("Ticker")["PE"].to_dict()
    fundamentals = {}
    for ticker in tickers:
        fundamentals[ticker] = {
            "PE": pe_map.get(ticker, pd.NA),
            "ROE": pd.NA  # optional: skip or add from sheet later
        }

    df_fund = pd.DataFrame(fundamentals).T
    df_fund["Momentum Rank"] = momentum_rank
    df_fund["PE Rank"] = df_fund["PE"].rank(ascending=True)
    df_fund["ROE Rank"] = pd.NA
    df_fund["Combined Score"] = df_fund[["Momentum Rank", "PE Rank"]].mean(axis=1)

    df_fund = df_fund.sort_values("Combined Score").reset_index().rename(columns={"index": "Ticker"})
    df_fund["Signal"] = ""
    df_fund.loc[:9, "Signal"] = "BUY"

    self.analysis_df = df_fund.copy()
    self.signal_log = df_fund[df_fund["Signal"] == "BUY"].to_dict("records")
    
    def analyze_sell(self, df):
        # No sell logic for this strategy
        self.signal_log += []  # or just pass
