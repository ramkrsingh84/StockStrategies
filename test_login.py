import streamlit as st
import streamlit_authenticator as stauth

# ✅ Hardcoded config
config = {
    "credentials": {
        "usernames": {
            "ram": {
                "name": "Ram",
                "password": "yourpassword123"
            }
        }
    },
    "cookie": {
        "name": "auth_cookie",
        "key": "dma_dashboard",
        "expiry_days": 1
    }
}

hashed_pw = stauth.Hasher(["yourpassword123"]).generate()
print(hashed_pw)


# ✅ Create authenticator
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

# ✅ Rerun counter
if "counter" not in st.session_state:
    st.session_state.counter = 0
st.session_state.counter += 1
st.write("Rerun count:", st.session_state.counter)

# ✅ Login widget
name, authentication_status, username = authenticator.login("🔐 Login", "main")

st.write("authentication_status after:", authentication_status)
st.write("name after:", name)
st.write("username after:", username)
st.write("Rerun count after:", st.session_state.counter)

# ✅ Handle login states
if authentication_status is False:
    st.error("❌ Incorrect username or password")
elif authentication_status is None:
    st.warning("⚠️ Please enter your credentials")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome, {name} 👋")
    st.title("📈 DMA Signal Dashboard")
