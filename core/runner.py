import json
import pandas as pd
import streamlit as st
from core.fetcher import DataFetcher
from core.portfolio import PortfolioManager

class StrategyRunner:
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.analyzer = config["analyzer_class"](
            sell_threshold_pct=config.get("sell_threshold_pct", 12)
        )

        creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
        self.portfolio_mgr = PortfolioManager(config["sheet_name"], creds_dict)
        self.fetcher = DataFetcher(config["sheet_name"], creds_dict)

    def run(self):
        # Load portfolio
        portfolio_df = self.portfolio_mgr.load(self.config["portfolio_tab"])

        # Load buy candidates from multiple tabs
        buy_df = pd.concat(
            [self.fetcher.fetch(tab) for tab in self.config["buy_tabs"]],
            ignore_index=True
        ).drop_duplicates(subset=["Ticker"])

        # 🔑 Normalize column names to lowercase
        portfolio_df.columns = [str(c).strip().lower() for c in portfolio_df.columns]
        buy_df.columns = [str(c).strip().lower() for c in buy_df.columns]

        # 🔑 Ensure canonical names
        if "ticker" not in buy_df.columns and "ticker" in buy_df.columns:
            buy_df.rename(columns={"Ticker": "ticker"}, inplace=True)
        if "date" in portfolio_df.columns and "trade_date" not in portfolio_df.columns:
            portfolio_df.rename(columns={"date": "trade_date"}, inplace=True)

        # Run analyzer
        self.analyzer.analyze_buy(buy_df)
        self.analyzer.analyze_sell(portfolio_df)

        return pd.DataFrame(self.analyzer.signal_log)