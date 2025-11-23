import importlib
import pandas as pd
from supabase import create_client
import streamlit as st

class Nifty200RSIRunner:
    def __init__(self, config):
        self.config = config
        self.analyzer = None

        # Supabase connection
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        self.supabase = create_client(url, key)

    def run(self):
        # Dynamically import analyzer
        module = importlib.import_module("core.nifty200_rsi_analyzer")
        analyzer_class = getattr(module, "Nifty200RSIAnalyzer")
        self.analyzer = analyzer_class(self.supabase)

        # Load tickers from Google Sheet (same as other strategies)
        sheet_url = st.secrets["gsheets"]["url"]
        csv_url = sheet_url.replace("/edit#gid=", "/export?format=csv&gid=")
        tickers_df = pd.read_csv(csv_url)

        # Run analyzer
        self.analyzer.analyze_buy(tickers_df)