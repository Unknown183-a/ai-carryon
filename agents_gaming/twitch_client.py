# agents_gaming/twitch_client.py
"""
Thin wrapper around the Twitch Helix API.

Auth: app access token via the OAuth client-credentials flow (no user login
needed — this is enough for reading public clips/streams/games). Needs a
Twitch Developer app: https://dev.twitch.tv/console/apps
  TWITCH_CLIENT_ID
  TWITCH_CLIENT_SECRET

Token is cached in-memory for the life of the process and refreshed on 401.
"""
import os
import time
import requests

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
BASE_URL = "https://api.twitch.tv/helix"

_token_cache = {"access_token": None, "expires_at": 0}


def get_app_token():
    """Client-credentials app token, cached until ~60s before expiry."""
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set")

    r = requests.post(TOKEN_URL, params={
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }, timeout=20)
    r.raise_for_status()
    data = r.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def _headers():
    return {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {get_app_token()}",
    }


def _get(path, params=None, retry=True):
    r = requests.get(f"{BASE_URL}/{path}", headers=_headers(), params=params or {}, timeout=20)
    if r.status_code == 401 and retry:
        # token expired/invalid mid-life — force refresh once
        _token_cache["access_token"] = None
        return _get(path, params, retry=False)
    r.raise_for_status()
    return r.json()


def get_users(logins):
    """logins: list[str] of Twitch usernames -> list of user dicts (id, login, display_name)."""
    if not logins:
        return []
    out = []
    for i in range(0, len(logins), 100):  # Helix caps at 100 per call
        chunk = logins[i:i + 100]
        data = _get("users", params=[("login", l) for l in chunk])
        out.extend(data.get("data", []))
    return out


def get_top_games(limit=10):
    data = _get("games/top", params={"first": min(limit, 100)})
    return data.get("data", [])


def get_streams_by_user(user_logins):
    """Currently-live streams for a list of usernames (empty list if none live)."""
    if not user_logins:
        return []
    params = [("user_login", l) for l in user_logins[:100]]
    data = _get("streams", params=params)
    return data.get("data", [])


def get_clips(broadcaster_id=None, game_id=None, started_at=None, ended_at=None, limit=20):
    """One of broadcaster_id / game_id is required by Helix.
    started_at/ended_at: RFC3339 strings to scope the clip window (e.g. last 24h)
    for a genuinely 'trending in the last day' feel rather than all-time top clips."""
    if not broadcaster_id and not game_id:
        raise ValueError("get_clips needs broadcaster_id or game_id")
    params = {"first": min(limit, 100)}
    if broadcaster_id:
        params["broadcaster_id"] = broadcaster_id
    if game_id:
        params["game_id"] = game_id
    if started_at:
        params["started_at"] = started_at
    if ended_at:
        params["ended_at"] = ended_at
    data = _get("clips", params=params)
    return data.get("data", [])
