import streamlit as st
import os
import streamlit_authenticator as stauth

# ✅ Page setup
st.set_page_config(page_title="DMA Dashboard", layout="centered")

# ✅ Load credentials from secrets
credentials = {
    "usernames": {
        "ram": {
            "name": st.secrets["credentials"]["usernames"]["ram"]["name"],
            "password": st.secrets["credentials"]["usernames"]["ram"]["password"]
        }
    }
}

cookie_name = st.secrets["cookie"]["name"]
key = st.secrets["cookie"]["key"]
expiry_days = st.secrets["cookie"]["expiry_days"]

# ✅ Create authenticator
authenticator = stauth.Authenticate(credentials, cookie_name, key, expiry_days)

# ✅ Login widget
name, authentication_status, username = authenticator.login("🔐 Login", "main")

# ✅ Handle login states
if authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("⚠️ Please enter your credentials")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome, {name} 👋")

    # ✅ Store login status for subpages
    st.session_state["authentication_status"] = True
    st.session_state["username"] = username
    st.session_state["name"] = name

    # ✅ Homepage content
    st.title("📊 DMA Signal Dashboard")
    st.markdown("Choose a section to explore:")
    
    st.write("Current working directory:", os.getcwd())

    st.page_link("pages/1_BUY_Signals.py", label="🟢 View BUY Signals", icon="📈")
    st.page_link("pages/2_Portfolio_with_SELL.py", label="📊 Portfolio with SELL Triggers", icon="📦")
    st.page_link("pages/3_FD_Benchmark.py", label="📈 FD Benchmark Comparison", icon="💰")
    st.page_link("pages/4_Profit_Realization.py", label="📈 Profit Realization", icon="💰")


