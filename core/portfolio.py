import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from .columns import col

class PortfolioManager:
    def __init__(self, sheet_name, creds_dict):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        self.client = gspread.authorize(creds)
        self.sheet_name = sheet_name

    def load(self, tab_name):
        return self._load_tab_data(self.sheet_name, tab_name, self.client)

    @st.cache_data(ttl=300)  # ✅ Cache for 5 minutes
    def _load_tab_data(_sheet_name, _tab_name, _client):
        try:
            sheet = client.open(sheet_name).worksheet(tab_name)
            df = pd.DataFrame(sheet.get_all_records())
            if df.empty:
                return df

            df[col("ticker")] = df[col("ticker")].astype(str).str.upper()
            df[col("sell_date")] = pd.to_datetime(df[col("sell_date")], errors="coerce").dt.date
            df[col("buy_date")] = pd.to_datetime(df[col("buy_date")], errors="coerce").dt.date

            for c in [col("buy_price"), col("buy_qty"), col("current_price")]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            return df.dropna(subset=[
                col("ticker"),
                col("buy_price"),
                col("buy_qty"),
                col("current_price")
            ])
        except Exception as e:
            print(f"❌ Error loading portfolio tab '{tab_name}': {e}")
            return pd.DataFrame()