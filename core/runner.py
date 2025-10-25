import pandas as pd
import streamlit as st
import json
from .portfolio import PortfolioManager
from .fetcher import DataFetcher

class StrategyRunner:
    def __init__(self, name, config):
        self.name = name
        self.config = config

        # ✅ Analyzer setup
        self.analyzer = config["analyzer_class"](
            sell_threshold_pct=config.get("sell_threshold_pct", 12)
        )

        # ✅ Load credentials from secrets
        creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])

        # ✅ Inject credentials into managers
        self.portfolio_mgr = PortfolioManager(config["sheet_name"], creds_dict)
        self.fetcher = DataFetcher(config["sheet_name"], creds_dict)

    def run(self):
        # ✅ Load portfolio and BUY tabs
        portfolio_df = self.portfolio_mgr.load(self.config["portfolio_tab"])
        buy_df = pd.concat(
            [self.fetcher.fetch(tab) for tab in self.config["buy_tabs"]],
            ignore_index=True
        ).drop_duplicates(subset=["Ticker"])

        # ✅ Run analysis
        self.analyzer.analyze_buy(buy_df)
        self.analyzer.analyze_sell(portfolio_df)

        return pd.DataFrame(self.analyzer.signal_log)