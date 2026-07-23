import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

# Needs both scopes: upload (for posting videos) and readonly (for view
# tracking's channels/playlists/videos.list calls) — a token minted with
# only youtube.upload will 403 with insufficientPermissions on read calls.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("cricket_token.pickle", "wb") as f:
    pickle.dump(creds, f)

with open("cricket_token.pickle", "rb") as f:
    token_bytes = f.read()

print("\n--- COPY THIS INTO CRICKET_YOUTUBE_TOKEN_B64 (Secret Manager) ---\n")
print(base64.b64encode(token_bytes).decode())
