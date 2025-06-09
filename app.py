import streamlit as st
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
import io

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BASE_URL      = "http://54.184.236.96"
LOGIN_URL     = BASE_URL + "/accounts/login/"
PUSH_ADD_URL  = BASE_URL + "/job/push_template_add"
PUSH_LIST_URL = BASE_URL + "/job/push_template"

CDN_OLD = "s3://dragon-business-res"
CDN_NEW = "https://d1i7uj8b98if3u.cloudfront.net"

# ─── CREDENTIAL INPUT ─────────────────────────────────────────────────────────
defaults = st.secrets.get("credentials", {})
username = st.text_input("Username", value=defaults.get("username",""))
password = st.text_input("Password", type="password", value=defaults.get("password",""))

st.title("Auto-Template Pusher (Requests Edition)")

# ─── FILE UPLOADER ─────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload your template-details Excel", type="xlsx")
if not uploaded:
    st.stop()

df = pd.read_excel(uploaded, dtype=str)
st.write("Detected columns:", df.columns.tolist())

# ─── PUSH BUTTON ───────────────────────────────────────────────────────────────
if st.button("Push All Templates"):
    session = requests.Session()

    # 1) GET login page to read CSRF
    r = session.get(LOGIN_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    csrf = soup.find("input", {"name":"csrfmiddlewaretoken"})["value"]

    # 2) POST login
    session.post(
        LOGIN_URL,
        data={"csrfmiddlewaretoken": csrf,
              "username": username,
              "password": password},
        headers={"Referer": LOGIN_URL}
    )

    payload_records = []
    id_records      = []

    # 3) Iterate rows
    for _, row in df.iterrows():
        name   = row["Template Name"]
        title  = row["Title"]
        body   = row["Message"]
        imgurl = row["Image URL"].replace(CDN_OLD, CDN_NEW)
        launch = row["Launch URL"].replace(CDN_OLD, CDN_NEW)

        # GET the add-template page to refresh CSRF
        r = session.get(PUSH_ADD_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        csrf = soup.find("input", {"name":"csrfmiddlewaretoken"})["value"]

        # Build form data
        data = {
            "csrfmiddlewaretoken": csrf,
            "name": name,
            "title": title,
            "text": body,
            "image-url": imgurl,
            "launch-url": launch,
        }

        # extras: bg1, bg2, track, onlybg
        extras = {}
        for col in ["bg1","bg2","track","onlybg"]:
            if col in row and pd.notna(row[col]):
                extras[col] = row[col].replace(CDN_OLD, CDN_NEW)

        # Include extras fields in the POST body
        for i, (k,v) in enumerate(extras.items()):
            data[f"payload_key_{i}"]   = k
            data[f"payload_value_{i}"] = v

        # Perform the POST
        session.post(
            PUSH_ADD_URL,
            data=data,
            headers={"Referer": PUSH_ADD_URL}
        )

        # 4) Fetch the listing page to find the new ID
        r = session.get(PUSH_LIST_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        # look for a div.card-header containing the template name
        header = soup.find("div", class_="card-header", string=lambda t: name in t)
        tid = header.get_text().split(":")[0].strip()
        id_records.append({"Template Name": name, "Template ID": tid})

        # 5) Build the payload JSON record
        payload = {
            **extras,
            "title": title,
            "body": body,
            "bigImage": imgurl,
            "sound": extras.get("track","")
        }
        payload_records.append({
            "Template Name": name,
            "Payload JSON": json.dumps(payload, ensure_ascii=False)
        })

    # 6) Offer downloads
    df_payload = pd.DataFrame(payload_records)
    df_ids     = pd.DataFrame(id_records)

    # Excel in-memory for download
    buf1 = io.BytesIO()
    buf2 = io.BytesIO()
    df_payload.to_excel(buf1, index=False, engine="openpyxl")
    df_ids.to_excel(buf2, index=False, engine="openpyxl")
    buf1.seek(0); buf2.seek(0)

    st.download_button("Download payloads.xlsx", buf1, "payloads.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Download template_ids.xlsx", buf2, "template_ids.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
