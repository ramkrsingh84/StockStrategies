COLUMN_NAMES = {
    "ticker": "Ticker",
    "buy_date": "Buy Date",
    "sell_date": "Sell Date",
    "buy_price": "Buy Price",
    "buy_qty": "Buy Qty",
    "current_price": "Current Price",
    "last_close": "Yest. Closing",
    "min_6m": "6 Months Minimum*1.2",
    "dma_5": "5 DMA",
    "dma_20": "20 DMA",
    "dma_50": "50 DMA",
    "dma_100": "100 DMA",
    "dma_200": "200 DMA",
    "high_52w_date": "52 Week High Date",
    "low_52w_date": "52 Week Low Date"
}

def col(name):
    return COLUMN_NAMES.get(name, name)