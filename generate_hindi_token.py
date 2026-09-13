"""
Run this once locally to generate token_hindi.json for the Hindi channel.

IMPORTANT: Log into the Hindi channel's Google account in your browser
(or use an incognito window) before running this, so the OAuth consent
screen authenticates the correct YouTube channel — not your English one.
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secrets_hindi.json", SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": creds.scopes,
}

with open("token_hindi.json", "w") as f:
    json.dump(token_data, f, indent=2)

print("Saved token_hindi.json — you're set for the Hindi channel.")
