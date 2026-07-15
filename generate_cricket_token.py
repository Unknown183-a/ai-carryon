import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("cricket_token.pickle", "wb") as f:
    pickle.dump(creds, f)

with open("cricket_token.pickle", "rb") as f:
    token_bytes = f.read()

print("\n--- COPY THIS INTO RENDER AS CRICKET_YOUTUBE_TOKEN_B64 ---\n")
print(base64.b64encode(token_bytes).decode())
