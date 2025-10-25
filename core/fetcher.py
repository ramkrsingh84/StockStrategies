import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from .columns import col
import os
import json

        
class DataFetcher:
    def __init__(self, sheet_name, creds_dict):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        self.client = gspread.authorize(creds)
        self.sheet_name = sheet_name

    def fetch(self, tab_name):
        return self._fetch_tab_data(self.sheet_name, tab_name, self.client)

    @st.cache_data(ttl=300)  # ✅ Cache for 5 minutes
    def _fetch_tab_data(sheet_name, tab_name, client):
        try:
            sheet = client.open(sheet_name).worksheet(tab_name)
            raw = sheet.get_all_values()
            if not raw or len(raw) < 2:
                return pd.DataFrame()

            headers = [h.strip() for h in raw[0]]
            df = pd.DataFrame(raw[1:], columns=headers)
            df[col("ticker")] = df[col("ticker")].astype(str).str.upper()

            for c in df.columns:
                if any(k in c for k in ["Price", "DMA", "Closing", "Minimum"]):
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            return df.dropna(subset=[col("ticker"), col("current_price")])
        except Exception as e:
            print(f"❌ Error fetching tab '{tab_name}': {e}")
            return pd.DataFrame()
