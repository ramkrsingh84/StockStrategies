import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from .columns import col
import os
import json


class DataFetcher:
    def __init__(self, sheet_name):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        self.client = gspread.authorize(creds)
        self.sheet_name = sheet_name

    def fetch(self, tab_name):
        sheet = self.client.open(self.sheet_name).worksheet(tab_name)
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