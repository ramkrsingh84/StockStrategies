import streamlit as st
import streamlit_authenticator as stauth
import yaml

# ✅ Load config from YAML
with open("config.yaml") as file:
    config = yaml.safe_load(file)

# ✅ Create authenticator using legacy constructor
credentials = config["credentials"]
cookie_name = config["cookie"]["name"]
key = config["cookie"]["key"]
expiry_days = config["cookie"]["expiry_days"]

authenticator = stauth.Authenticate(
    credentials,
    cookie_name,
    key,
    expiry_days
)

# ✅ Rerun counter to verify execution
if "counter" not in st.session_state:
    st.session_state.counter = 0
st.session_state.counter += 1
st.write("🔁 Rerun count:", st.session_state.counter)

# ✅ Login widget
name, authentication_status, username = authenticator.login("🔐 Login", "main")

# ✅ Debug output
st.write("🧠 Username:", username)
st.write("🧠 Name:", name)
st.write("🧠 Authentication status:", authentication_status)

# ✅ Handle login states
if authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("⚠️ Please enter your credentials")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome, {name} 👋")
    st.title("📈 DMA Signal Dashboard")
    st.write("✅ You are now logged in.")