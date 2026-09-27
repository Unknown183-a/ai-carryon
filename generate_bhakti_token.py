"""
Run this once locally to generate token_bhakti.json for the Bhakti channel.

IMPORTANT: Log into the Bhakti channel's Google account in your browser
(or use an incognito window) before running this, so the OAuth consent
screen authenticates the correct YouTube channel — not your English or
Hindi one.

Prerequisite: download an OAuth client-secrets JSON from Google Cloud
Console (APIs & Services -> Credentials -> OAuth client ID -> Desktop app)
for the project tied to the Bhakti channel, save it as
client_secrets_bhakti.json in this directory.
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secrets_bhakti.json", SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": creds.scopes,
}

with open("token_bhakti.json", "w") as f:
    json.dump(token_data, f, indent=2)

print("Saved token_bhakti.json — you're set for the Bhakti channel.")
print("For deployment, base64-encode its contents (or paste raw JSON) into")
print("the BHAKTI_TOKEN_JSON environment variable.")
