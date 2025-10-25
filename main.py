import streamlit as st
from config import STRATEGY_CONFIG
from core.runner import StrategyRunner
from core.columns import col

st.set_page_config(page_title="DMA Signal Dashboard", layout="centered")
st.title("📈 DMA Signal Dashboard")

selected_strategy = st.selectbox("Choose Strategy", list(STRATEGY_CONFIG.keys()))
run_button = st.button("Run Strategy")

if run_button:
    with st.spinner("Running analysis..."):
        runner = StrategyRunner(selected_strategy, STRATEGY_CONFIG[selected_strategy])
        result_df = runner.run()

    if result_df.empty:
        st.success("✅ No actionable signals today.")
    else:
        # BUY signals
        buy_df = result_df[result_df["Signal"] == "BUY"]
        if not buy_df.empty:
            st.subheader("🟢 BUY Signals")
            st.dataframe(buy_df)

        # SELL signals merged into portfolio summary
        sell_df = result_df[result_df["Signal"] == "SELL"]
        portfolio_runner = StrategyRunner(selected_strategy, STRATEGY_CONFIG[selected_strategy])
        portfolio_df = portfolio_runner.portfolio_mgr.load(STRATEGY_CONFIG[selected_strategy]["portfolio_tab"])

        if not portfolio_df.empty:

            # Merge SELL signals into portfolio
            portfolio_df[col("ticker")] = portfolio_df[col("ticker")].astype(str).str.upper()
            sell_df.loc[:, "Signal"] = "SELL"
            merged = portfolio_df.merge(
                sell_df[[col("ticker"), "Signal", "P&L %", "Price"]],
                how="left",
                left_on=col("ticker"),
                right_on=col("ticker")
            )

            # Add a highlight column for styling
            merged["Highlight"] = merged["Signal"].apply(lambda x: "SELL" if x == "SELL" else "NORMAL")
            
            # Filter toggle
            show_only_sell = st.checkbox("🔻 Show only SELL-triggered holdings")

            if show_only_sell:
                filtered_df = merged[merged["Highlight"] == "SELL"]
            else:
                filtered_df = merged

            # Define styling function
            def highlight_sell(row):
                if row["Highlight"] == "SELL":
                    return ["background-color: #ffe6e6"] * len(row)  # light red
                else:
                    return [""] * len(row)

            # Apply styling
            styled_df = merged.style.apply(highlight_sell, axis=1)

            st.subheader("📊 Portfolio Summary with SELL Signals")
            st.dataframe(styled_df, width="stretch")
