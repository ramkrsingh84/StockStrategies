from core.analyzers import SignalAnalyzer, ConsolidateAnalyzer, MomentumValueAnalyzer

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
    "MomentumValue": {
        "sheet_name": "DMA_Data",
        "portfolio_tab": "Portfolio_MomentumValue",
        "buy_tabs": ["Nifty_200"],
        "analyzer_class": MomentumValueAnalyzer,
        "sell_threshold_pct": 12
    }
}