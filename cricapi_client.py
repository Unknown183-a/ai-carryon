import os
import requests
from dotenv import load_dotenv

load_dotenv()

CRICAPI_KEYS = [
    os.getenv("CRICAPI_KEY"),
    os.getenv("CRICAPI_KEY_2"),
]
CRICAPI_KEYS = [k for k in CRICAPI_KEYS if k]

def cricapi_get(endpoint: str, params: dict, timeout: int = 20):
    base_url = f"https://api.cricapi.com/v1/{endpoint}"
    for i, key in enumerate(CRICAPI_KEYS):
        call_params = {**params, "apikey": key}
        try:
            r = requests.get(base_url, params=call_params, timeout=timeout)
            data = r.json()
        except Exception as e:
            print(f"[cricapi_get] Key {i+1} request failed: {e}")
            continue

        if data.get("status") == "success":
            return data

        reason = data.get("reason", "")
        if any(x in reason.lower() for x in ["hits", "limit", "block"]):
            print(f"[cricapi_get] Key {i+1} quota exhausted, trying next key...")
            continue
        else:
            print(f"[cricapi_get] Key {i+1} failed with non-quota reason: {reason}")
            return data

    print("[cricapi_get] All keys exhausted or failed.")
    return None

if __name__ == "__main__":
    data = cricapi_get("match_scorecard", {"id": "a5ecf1bb-1f8c-4a4d-9165-67aa61af2ea2"})
    print(data)
