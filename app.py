import streamlit as st
import pandas as pd
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIG ───────────────────────────────────────────────────
LOGIN_URL     = "http://54.184.236.96/accounts/login/"
PUSH_ADD_URL  = "http://54.184.236.96/job/push_template_add"
PUSH_LIST_URL = "http://54.184.236.96/job/push_template"

CDN_OLD = "s3://dragon-business-res"
CDN_NEW = "https://d1i7uj8b98if3u.cloudfront.net"

# ─── CREDENTIAL INPUT ──────────────────────────────────────────
default_user = st.secrets["credentials"].get("username", "")
default_pass = st.secrets["credentials"].get("password", "")

st.title("Auto-Template Pusher")
username = st.text_input("Username", value=default_user)
password = st.text_input("Password", type="password", value=default_pass)

# ─── FILE UPLOADER ─────────────────────────────────────────────
uploaded = st.file_uploader("Upload your template-details Excel", type="xlsx")
if not uploaded:
    st.stop()

df = pd.read_excel(uploaded, dtype=str)
st.write("Detected columns:", df.columns.tolist())

# ─── BUTTON TO PUSH ────────────────────────────────────────────
if st.button("Push All Templates"):
    driver = webdriver.Chrome(ChromeDriverManager().install(),
                              options=webdriver.ChromeOptions().add_argument("--headless=new"))
    wait = WebDriverWait(driver, 10)

    # 1) Login
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(username)
    driver.find_element(By.ID, "id_password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()

    payload_records, id_records = [], []

    # 2) Iterate rows
    for _, row in df.iterrows():
        name   = row["Template Name"]
        title  = row["Title"]
        body   = row["Message"]
        imgurl = row["Image URL"].replace(CDN_OLD, CDN_NEW)
        launch = row["Launch URL"].replace(CDN_OLD, CDN_NEW)

        extras = {}
        for col in ["bg1", "bg2", "track", "onlybg"]:
            if col in row and pd.notna(row[col]):
                extras[col] = row[col].replace(CDN_OLD, CDN_NEW)

        # a) Add template
        driver.get(PUSH_ADD_URL)
        wait.until(EC.presence_of_element_located((By.ID, "name"))).send_keys(name)
        driver.find_element(By.ID, "title").send_keys(title)
        driver.find_element(By.ID, "text").send_keys(body)
        driver.find_element(By.ID, "image-url").send_keys(imgurl)
        driver.find_element(By.ID, "launch-url").send_keys(launch)

        for i, (k, v) in enumerate(extras.items()):
            driver.find_element(By.ID, "add-payload-field").click()
            driver.find_element(By.NAME, f"payload_key_{i}").send_keys(k)
            driver.find_element(By.NAME, f"payload_value_{i}").send_keys(v)

        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # b) Fetch ID
        driver.get(PUSH_LIST_URL)
        header = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"//div[@class='card-header' and contains(., '{name}')]")
        ))
        tid = header.text.split(":")[0].strip()
        id_records.append({"Template Name": name, "Template ID": tid})

        # c) Build payload JSON
        payload = {**extras, "title": title, "body": body,
                   "bigImage": imgurl, "sound": extras.get("track", "")}
        payload_records.append({
            "Template Name": name,
            "Payload JSON": json.dumps(payload, ensure_ascii=False)
        })

    driver.quit()

    # 3) Download buttons
    df_payload = pd.DataFrame(payload_records)
    df_ids     = pd.DataFrame(id_records)

    st.download_button(
        "Download payloads.xlsx",
        df_payload.to_excel(index=False, engine="openpyxl"),
        file_name="payloads.xlsx"
    )
    st.download_button(
        "Download template_ids.xlsx",
        df_ids.to_excel(index=False, engine="openpyxl"),
        file_name="template_ids.xlsx"
    )
