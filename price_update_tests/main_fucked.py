import os
import re
import base64
import datetime
import logging
import csv
import json
import time
import uuid
from pathlib import Path
from io import BytesIO

import requests
import pandas as pd
from flask import jsonify, Request
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from google.cloud import storage

# --- Config ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TMP_DIR = Path("/tmp")
CONFIG_PATH = Path("config/venues.json")
BUCKET_NAME = "price-update-csvs"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger()

# --- Gmail Authentication ---
def authenticate_gmail():
    creds = None
    if Path('token.json').exists():
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# --- Find Attachments ---
def find_attachments_recursively(parts):
    attachments = []
    for part in parts:
        filename = part.get("filename", "")
        if filename.lower().endswith(".xlsx") and "attachmentId" in part.get("body", {}):
            attachments.append({"filename": filename, "attachmentId": part["body"]["attachmentId"]})
        elif part.get("parts"):
            attachments.extend(find_attachments_recursively(part["parts"]))
    return attachments

# --- Upload to GCS ---
def upload_to_gcs(file_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_path.name)
    blob.upload_from_filename(str(file_path))
    log.info(f"✅ Uploaded to GCS: {file_path.name}")

# --- Clean Excel and Save ---
def clean_and_convert_to_csv(excel_bytes, original_filename):
    try:
        df = pd.read_excel(BytesIO(excel_bytes), engine="openpyxl")
        df.columns.values[0] = 'merchant_sku'
        df.columns.values[1] = 'price'
        df['price'] = pd.to_numeric(df['price'], errors='coerce')

        if 'Vekt pr stykk' in df.columns and 'Mengdeintervall' in df.columns:
            for idx, row in df.iterrows():
                base = row['price']
                weight = row.get('Vekt pr stykk')
                amount = row.get('Mengdeintervall')
                if pd.notna(weight):
                    df.at[idx, 'price'] = round(base * weight, 2)
                elif pd.notna(amount):
                    df.at[idx, 'price'] = round(base * amount, 2)

        df.drop_duplicates(subset=["merchant_sku"], inplace=True)

        cleaned_name = Path(original_filename).stem + "_cleaned.csv"
        cleaned_path = TMP_DIR / cleaned_name
        df[["merchant_sku", "price"]].to_csv(cleaned_path, index=False)

        upload_to_gcs(cleaned_path)
        return cleaned_path

    except Exception as e:
        log.warning(f"❌ Failed to clean: {original_filename} — {e}")
        return None

# --- Gmail Fetch ---
def fetch_and_clean_from_gmail():
    service = authenticate_gmail()
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    after = yesterday.strftime("%Y/%m/%d")
    before = (yesterday + datetime.timedelta(days=1)).strftime("%Y/%m/%d")
    query = f'subject:"Wolt kalkyledato" has:attachment after:{after} before:{before}'

    log.info(f"🔍 Gmail query: {query}")
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    cleaned_files = []

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        parts = msg_data.get('payload', {}).get('parts', [])
        attachments = find_attachments_recursively(parts)

        for attachment_info in attachments:
            filename = attachment_info['filename']
            cleaned_path = TMP_DIR / (Path(filename).stem + "_cleaned.csv")
            if cleaned_path.exists():
                continue
            attachment = service.users().messages().attachments().get(
                userId='me', messageId=msg['id'], id=attachment_info['attachmentId']
            ).execute()
            file_data = base64.urlsafe_b64decode(attachment['data'])
            cleaned_csv = clean_and_convert_to_csv(file_data, filename)
            if cleaned_csv:
                cleaned_files.append(cleaned_csv)

    return cleaned_files

# --- GCS Lookup for Today's Files ---
def get_today_csvs_from_gcs():
    today = datetime.date.today()
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())

    today_files = []
    for blob in blobs:
        match = re.search(r'(\d{2}\.\d{2}\.\d{2})', blob.name)
        if match:
            try:
                file_date = datetime.datetime.strptime(match.group(1), "%d.%m.%y").date()
                if file_date == today:
                    local_path = TMP_DIR / f"{uuid.uuid4()}_{Path(blob.name).name}"
                    blob.download_to_filename(str(local_path))
                    today_files.append(local_path)
                    log.info(f"📄 Downloaded for today: {blob.name}")
            except ValueError:
                continue
    return today_files

# --- Load Price Updates ---
def load_all_price_updates(csv_files):
    all_items = {}
    for csv_path in csv_files:
        log.info(f"📄 Reading: {csv_path.name}")
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sku = row["merchant_sku"].strip()
                    price_eur = float(row["price"])
                    price_cents = int(price_eur * 100)
                    all_items[sku] = price_cents
                except Exception as e:
                    log.warning(f"⚠️ Skipping row in {csv_path.name}: {e}")
    return [{"gtin": sku, "price": price} for sku, price in all_items.items()]

# --- Update Venue ---
def update_venue(venue, items):
    url = f"https://pos-integration-service.wolt.com/venues/{venue['id']}/items"
    payload = {"data": items}
    log.info(f"📡 Sending update to {venue['name']} (ID: {venue['id']})...")
    try:
        response = requests.patch(
            url,
            auth=(venue["username"], venue["password"]),
            headers={"Content-Type": "application/json"},
            json=payload
        )
        if response.status_code == 202:
            log.info(f"✅ Success: Updated {len(items)} items")
        elif response.status_code == 429:
            log.warning("🔁 Rate limited by Wolt (429). Consider retrying later.")
        else:
            log.error(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        log.error(f"🚨 Network error: {e}")

# --- Core Logic ---
def run_update_process():
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    venues = config["venues"]

    fetch_and_clean_from_gmail()
    relevant_files = get_today_csvs_from_gcs()

    if not relevant_files:
        log.warning("⚠️ No relevant CSVs for today.")
        return

    items = load_all_price_updates(relevant_files)
    if not items:
        log.warning("⚠️ No valid items found in CSVs.")
        return

    for venue in venues:
        update_venue(venue, items)
        time.sleep(1)

    log.info(f"🎯 Update process completed for {len(venues)} venue(s).")

# --- HTTP Entry Point ---
def main(request: Request):
    try:
        run_update_process()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        log.exception("Unhandled error")
        return jsonify({"status": "error", "message": str(e)}), 500
