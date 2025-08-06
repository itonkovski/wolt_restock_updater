import os
import base64
import datetime
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import pandas as pd
from io import BytesIO

# --- Setup ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DATA_DIR = Path("data")
LOG_DIR = Path("logs")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# --- Logging ---
logging.basicConfig(
    filename=LOG_DIR / "fetch_mail.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger()

# --- Auth ---
def authenticate_gmail():
    creds = None
    if Path('token.json').exists():
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# --- Attachment Search ---
def find_attachments_recursively(parts):
    attachments = []
    for part in parts:
        filename = part.get("filename", "")
        if filename.lower().endswith(".xlsx") and "attachmentId" in part.get("body", {}):
            attachments.append({
                "filename": filename,
                "attachmentId": part["body"]["attachmentId"]
            })
        elif part.get("parts"):
            attachments.extend(find_attachments_recursively(part["parts"]))
    return attachments

# --- Clean Logic ---
def clean_and_convert_to_csv(excel_bytes, original_filename):
    try:
        df = pd.read_excel(BytesIO(excel_bytes), engine="openpyxl")

        # Rename columns
        df.columns.values[0] = 'merchant_sku'
        df.columns.values[1] = 'price'
        df['price'] = pd.to_numeric(df['price'], errors='coerce')

        # Calculate adjusted prices
        if 'Vekt pr stykk' in df.columns and 'Mengdeintervall' in df.columns:
            for idx, row in df.iterrows():
                base = row['price']
                weight = row.get('Vekt pr stykk')
                amount = row.get('Mengdeintervall')
                if pd.notna(weight):
                    df.at[idx, 'price'] = round(base * weight, 2)
                elif pd.notna(amount):
                    df.at[idx, 'price'] = round(base * amount, 2)

        # Remove duplicates
        df.drop_duplicates(subset=["merchant_sku"], inplace=True)

        # Save cleaned file
        cleaned_name = Path(original_filename).stem + "_cleaned.csv"
        cleaned_path = DATA_DIR / cleaned_name
        df[['merchant_sku', 'price']].to_csv(cleaned_path, index=False)

        print(f"✅ Cleaned and saved: {cleaned_name}")
        log.info(f"Saved cleaned CSV: {cleaned_name}")

    except Exception as e:
        print(f"❌ Failed to clean: {original_filename}")
        log.error(f"Cleaning failed for {original_filename}: {e}")

# --- Main Logic ---
def fetch_yesterdays_emails():
    service = authenticate_gmail()
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    after = yesterday.strftime("%Y/%m/%d")
    before = (yesterday + datetime.timedelta(days=1)).strftime("%Y/%m/%d")
    query = f'subject:"Wolt kalkyledato" has:attachment after:{after} before:{before}'
    print(f"🔍 Gmail query: {query}")
    log.info(f"Running query: {query}")

    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        if not messages:
            print("❌ No matching emails found for yesterday.")
            log.info("No emails found.")
            return

        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(no subject)')
            print(f"📬 Found email: {subject}")
            log.info(f"Found email: {subject}")

            parts = payload.get('parts', [])
            attachments = find_attachments_recursively(parts)

            if not attachments:
                print("⚠️ No Excel attachments found in this message.")
                log.warning("No Excel attachments found.")
                continue

            for attachment_info in attachments:
                filename = attachment_info['filename']
                cleaned_path = DATA_DIR / (Path(filename).stem + "_cleaned.csv")

                if cleaned_path.exists():
                    print(f"⏩ Skipping — already cleaned: {cleaned_path.name}")
                    log.info(f"Skipping cleaned file: {cleaned_path.name}")
                    continue

                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg['id'], id=attachment_info['attachmentId']
                ).execute()

                file_data = base64.urlsafe_b64decode(attachment['data'])
                clean_and_convert_to_csv(file_data, filename)

    except HttpError as error:
        print(f'🚨 Gmail API error: {error}')
        log.error(f"Gmail API error: {error}")

if __name__ == "__main__":
    fetch_yesterdays_emails()
