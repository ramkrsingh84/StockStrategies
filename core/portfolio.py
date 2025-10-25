import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from core.columns import col
import json

class PortfolioManager:
    def __init__(self, sheet_name, creds_dict):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        self.client = gspread.authorize(creds)
        self.sheet_name = sheet_name

    def load(self, tab_name):
        records = _load_raw_records(self.sheet_name, tab_name)
        df = pd.DataFrame(records)
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

@st.cache_data(ttl=300, show_spinner=True)
def _load_raw_records(sheet_name, tab_name):
    client = gspread.service_account_from_dict(json.loads(st.secrets["GOOGLE_CREDS_JSON"]))
    sheet = client.open(sheet_name).worksheet(tab_name)
    return sheet.get_all_records()