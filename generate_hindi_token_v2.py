"""
Run this locally to regenerate the Hindi channel's YouTube OAuth token
after it breaks (e.g. "invalid_client" errors from GitHub Actions).

Requirements:
  - client_secrets_hindi.json must be in this same folder.
  - pip install google-auth-oauthlib google-api-python-client

Usage:
  python generate_hindi_token_v2.py

It opens your browser to log in to the Google account that owns the
HINDI YouTube channel (careful if you're signed into multiple Google
accounts — pick the right one). After approving access, it prints a
JSON string — paste that whole JSON string (not base64, the raw JSON)
as the new value of the YOUTUBE_TOKEN_JSON secret in GitHub (or
HINDI_TOKEN_JSON, whichever one your repo actually reads first).

Unlike the English token flow, agents_hindi/upload_agent.py reads
client_id/client_secret directly out of this JSON blob rather than a
separate client_secrets file, which is exactly why this script writes
those fields into the output explicitly.
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Matches SCOPES_READ in agents_hindi/upload_agent.py — a token with
# both scopes covers upload AND view tracking / comment replies with
# a single credential, so you don't need to redo this twice.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secrets_hindi.json", SCOPES
)
creds = flow.run_local_server(port=0)

token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": creds.scopes,
}

token_json = json.dumps(token_data)

with open("token_hindi.json", "w") as f:
    f.write(token_json)

print("\n\n=== COPY EVERYTHING BELOW THIS LINE ===\n")
print(token_json)
print("\n=== COPY EVERYTHING ABOVE THIS LINE ===\n")
print("Paste that raw JSON (not base64) as the new value of the")
print("YOUTUBE_TOKEN_JSON secret on GitHub (also update HINDI_TOKEN_JSON")
print("if you want to keep both secrets populated and in sync).")
