from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json

# --- Settings ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def main():
    print("🌐 Starting Gmail auth flow...")
    
    # Load credentials and start the flow
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Save the token to file
    with open(TOKEN_FILE, 'w') as token_file:
        token_file.write(creds.to_json())

    print(f"✅ New token saved to {TOKEN_FILE}")

if __name__ == '__main__':
    main()
