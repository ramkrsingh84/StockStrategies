import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from .columns import col
import os
import json


class PortfolioManager:
    def __init__(self, sheet_name):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if creds_json is None:
            raise ValueError("❌ GOOGLE_CREDS_JSON not found in environment. Check Secrets Manager.")
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        self.client = gspread.authorize(creds)
        self.sheet_name = sheet_name

    def load(self, tab_name):
        sheet = self.client.open(self.sheet_name).worksheet(tab_name)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty:
            return df

        df[col("ticker")] = df[col("ticker")].astype(str).str.upper()
        df[col("sell_date")] = pd.to_datetime(df[col("sell_date")], errors="coerce").dt.date
        df[col("buy_date")] = pd.to_datetime(df[col("buy_date")], errors="coerce").dt.date
        for c in [col("buy_price"), col("buy_qty"), col("current_price")]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.dropna(subset=[col("ticker"), col("buy_price"), col("buy_qty"), col("current_price")])