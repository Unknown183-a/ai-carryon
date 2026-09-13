"""
Run this locally (not in GitHub Actions) to regenerate the YouTube OAuth
token for the English channel after it expires or gets revoked.

Requirements:
  - client_secrets.json must be in this same folder (the OAuth client
    credentials downloaded from Google Cloud Console).
  - pip install google-auth-oauthlib google-api-python-client

Usage:
  python generate_english_token.py

It will open your browser to log in to the Google account that owns
the English YouTube channel. After you approve access, it prints a
base64 string — paste that whole string as the new value of the
YOUTUBE_TOKEN_B64 secret in GitHub.
"""
import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.pickle", "wb") as f:
    pickle.dump(creds, f)

with open("token.pickle", "rb") as f:
    token_b64 = base64.b64encode(f.read()).decode("utf-8")

print("\n\n=== COPY EVERYTHING BELOW THIS LINE ===\n")
print(token_b64)
print("\n=== COPY EVERYTHING ABOVE THIS LINE ===\n")
print("Paste that as the new value of the YOUTUBE_TOKEN_B64 secret on GitHub.")
