import streamlit as st

st.title("Home")
st.page_link("pages/test.py", label="Go to test")


## ✅ Load config from secrets
#credentials = {
#    "usernames": {
#        "ram": {
#            "name": st.secrets["credentials"]["usernames"]["ram"]["name"],
#            "password": st.secrets["credentials"]["usernames"]["ram"]["password"]
#        }
#    }
#}
#
#cookie_name = st.secrets["cookie"]["name"]
#key = st.secrets["cookie"]["key"]
#expiry_days = st.secrets["cookie"]["expiry_days"]
#
## ✅ Create authenticator
#authenticator = stauth.Authenticate(
#    credentials,
#    cookie_name,
#    key,
#    expiry_days
#)
#
## ✅ Rerun counter to verify execution
#if "counter" not in st.session_state:
#    st.session_state.counter = 0
#st.session_state.counter += 1
#st.write("🔁 Rerun count:", st.session_state.counter)
#
## ✅ Login widget
#name, authentication_status, username = authenticator.login("🔐 Login", "main")
#
## ✅ Debug output
#st.write("🧠 Username:", username)
#st.write("🧠 Name:", name)
#st.write("🧠 Authentication status:", authentication_status)
#
## ✅ Handle login states
#if authentication_status is False:
#    st.error("❌ Incorrect username or password")
#elif authentication_status is None:
#    st.warning("⚠️ Please enter your credentials")
#elif authentication_status:
#    authenticator.logout("Logout", "sidebar")
#    st.sidebar.success(f"Welcome, {name} 👋")
#    st.title("📈 DMA Signal Dashboard")
#    st.write("✅ You are now logged in.")