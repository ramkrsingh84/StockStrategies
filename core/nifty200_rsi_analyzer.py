import pandas as pd

class Nifty200RSIAnalyzer:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.analysis_df = pd.DataFrame()

    def compute_rsi(self, series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def analyze_buy(self, tickers_df):
        results = []
        for _, row in tickers_df.iterrows():
            ticker = str(row["Ticker"]).strip().upper() + ".NS"
            peg = row.get("PEG", "NA")

            resp = self.supabase.table("ohlc_data").select("*").eq(
                "ticker", ticker
            ).order("trade_date", desc=True).limit(30).execute()
            records = resp.data
            if not records:
                continue

            df = pd.DataFrame(records).sort_values("trade_date")
            df["RSI"] = self.compute_rsi(df["close"])

            latest_rsi = df["RSI"].iloc[-1]
            prev_rsi = df["RSI"].iloc[-2]

            if (34 <= prev_rsi <= 36) and (latest_rsi >= 40):
                results.append({
                    "Ticker": ticker,
                    "RSI": round(latest_rsi, 2),
                    "PEG": peg
                })

        self.analysis_df = pd.DataFrame(results)
        return self.analysis_df

    def get_sheet_summary(self):
        return self.analysis_df