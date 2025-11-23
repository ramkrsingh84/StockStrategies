from core.analyzers import SignalAnalyzer, ConsolidateAnalyzer, TrendingValueAnalyzer, GARPAnalyzer, Nifty200RSIAnalyzer


STRATEGY_CONFIG = {
    "DMA": {
        "sheet_name": "DMA_Data",
        "portfolio_tab": "Portfolio_DMA",
        "buy_tabs": ["Nifty_50", "Nifty_200", "NiftyMidSmallCap_400", "Bank_Nifty"],
        "analyzer_class": SignalAnalyzer,
        "sell_threshold_pct": 12
    },
    "Consolidate_500_Stocks": {
        "sheet_name": "DMA_Data",
        "portfolio_tab": "Portfolio_500",
        "buy_tabs": ["Top_500_Stocks"],
        "analyzer_class": ConsolidateAnalyzer,
        "sell_threshold_pct": 12
    },
    "TrendingValue": {
        "sheet_name": "DMA_Data",
        "portfolio_tab": "Portfolio_TrendingValue",
        "buy_tabs": ["TrendingValueStocks"],
        "analyzer_class": TrendingValueAnalyzer,
        "sell_threshold_pct": 12
    },
    "GARP": {
        "sheet_name": "DMA_Data",
        "portfolio_tab": "Portfolio_GARP",
        "buy_tabs": ["GARPStocks"],
        "analyzer_class": GARPAnalyzer,
        "sell_threshold_pct": 12
    },
    "Nifty200_RSI": {
        "analyzer_class": "Nifty200RSIAnalyzer",
        "sheet_name": "Nifty_200"   # your Google Sheet name
    }

}