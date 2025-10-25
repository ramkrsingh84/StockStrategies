import pandas as pd
from .portfolio import PortfolioManager
from .fetcher import DataFetcher

class StrategyRunner:
    def __init__(self, name, config, creds_file="google_creds.json"):
        self.name = name
        self.config = config
        self.analyzer = config["analyzer_class"](sell_threshold_pct=config.get("sell_threshold_pct", 12))
        self.portfolio_mgr = PortfolioManager(config["sheet_name"], creds_file)
        self.fetcher = DataFetcher(config["sheet_name"], creds_file)

    def run(self):
        portfolio_df = self.portfolio_mgr.load(self.config["portfolio_tab"])
        buy_df = pd.concat([
            self.fetcher.fetch(tab) for tab in self.config["buy_tabs"]
        ], ignore_index=True).drop_duplicates(subset=["Ticker"])

        self.analyzer.analyze_buy(buy_df)
        self.analyzer.analyze_sell(portfolio_df)

        return pd.DataFrame(self.analyzer.signal_log)