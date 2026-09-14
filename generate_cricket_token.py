"""
generate_cricket_token.py — run this ONCE, locally, on your own machine.

What it does:
  1. Opens a browser for Google's OAuth consent screen
  2. You log in AS THE CRICKET CHANNEL'S Google account (not your personal one!)
  3. Approves access
  4. Pickles the resulting credentials and base64-encodes them
  5. Prints the string to paste into the CRICKET_YOUTUBE_TOKEN_B64 GitHub secret

Before running:
  - Put your client_secrets.json (from Google Cloud Console -> APIs & Services
    -> Credentials -> OAuth 2.0 Client ID -> Desktop app) in the same folder
    as this script. You almost certainly already have one from setting up
    English/Hindi's upload — reuse the same file.
  - pip install google-auth-oauthlib   (already in requirements_cricket.txt,
    but you're running this locally / outside the repo's venv is fine too)

Run:
  python generate_cricket_token.py
"""

import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

# Matches agents_cricket/upload_agent.py's SCOPES_READ — includes both upload
# and readonly so view tracking works too, not just uploading.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
creds = flow.run_local_server(port=0)

pickled = pickle.dumps(creds)
b64_string = base64.b64encode(pickled).decode()

print("\n" + "=" * 60)
print("COPY EVERYTHING BELOW THIS LINE INTO CRICKET_YOUTUBE_TOKEN_B64:")
print("=" * 60)
print(b64_string)
print("=" * 60)

with open("cricket_token_b64.txt", "w") as f:
    f.write(b64_string)
print("\n(Also saved to cricket_token_b64.txt in this folder, in case the terminal truncates it)")
