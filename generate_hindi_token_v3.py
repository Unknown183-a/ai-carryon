"""
Run this locally to regenerate the Hindi channel's YouTube OAuth token
with the full scope set (upload + readonly + force-ssl), needed after
adding youtube.force-ssl to SCOPES_READ (fixes comment-reply 403s).

Requirements:
  - client_secrets_hindi.json must be in this same folder.
  - pip install google-auth-oauthlib google-api-python-client

Usage:
  python3 generate_hindi_token_v3.py

Log in with the Hindi channel's Google account when the browser opens.
Paste the printed JSON (raw, with braces) as the new value of the
YOUTUBE_TOKEN_JSON secret on GitHub.
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
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
print("Paste that raw JSON (with braces) as the new value of the")
print("YOUTUBE_TOKEN_JSON secret on GitHub.")
