import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
import streamlit as st

def refresh_all_sheets(strategy_config):
    
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    try:
        refresh_sheet = client.open_by_key(client.open(strategy_config[list(strategy_config.keys())[0]]["sheet_name"]).id).worksheet("Refresh")
        refresh_sheet.update_acell("A1", str(pd.Timestamp.now()))
    except Exception as e:
        st.warning(f"⚠️ Failed to trigger refresh in 'Refresh' sheet: {e}")