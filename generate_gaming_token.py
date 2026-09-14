"""
Run this locally (not in GitHub Actions) to generate the YouTube OAuth
token for the Gaming channel.

Requirements:
  - client_secrets_gaming.json in this folder (OAuth client credentials
    downloaded from Google Cloud Console for the Gaming channel's YouTube
    Data API app — create a new OAuth client, don't reuse English's).
  - Log into the Gaming channel's Google account in your browser (or use an
    incognito window) before running this, so consent authenticates the
    right channel.

Usage:
  python generate_gaming_token.py

Prints a base64 string — paste it as the YOUTUBE_GAMING_TOKEN_B64 GitHub
Secret.
"""
import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secrets_gaming.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token_gaming.pickle", "wb") as f:
    pickle.dump(creds, f)

with open("token_gaming.pickle", "rb") as f:
    token_b64 = base64.b64encode(f.read()).decode("utf-8")

print("\n\n=== COPY EVERYTHING BELOW THIS LINE ===\n")
print(token_b64)
print("\n=== COPY EVERYTHING ABOVE THIS LINE ===\n")
print("Paste that as the new value of the YOUTUBE_GAMING_TOKEN_B64 secret on GitHub.")
print("Also base64-encode client_secrets_gaming.json itself (same way English's "
      "YOUTUBE_CLIENT_SECRETS_B64 secret was made) for YOUTUBE_GAMING_CLIENT_SECRETS_B64.")
