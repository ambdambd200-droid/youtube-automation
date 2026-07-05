"""
VARY YouTube Re-Authentication Tool

Runs the full OAuth 2.0 flow to get a fresh refresh token.
Ensures BOTH 'youtube.upload' and 'youtube' scopes are included
(required for thumbnail uploading).

Usage:
    python scripts/re_auth_youtube.py

Will open a browser window for you to authorize. The new token
is saved to upload_token.pickle and the refresh token is printed
so you can update your .env file.
"""
import json
import os
import sys
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET


SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "upload_token.pickle"
)


def re_authenticate():
    """Run interactive OAuth flow and save the resulting refresh token."""
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print("ERROR: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env")
        print("Make sure C:\\Users\\A\\Desktop\\Movies\\.env has these values.")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob",
                                  "http://localhost"]
            }
        },
        SCOPES
    )

    print("Opening browser for YouTube authorization...")
    print(f"Scopes requested: {SCOPES}")
    creds = flow.run_local_server(port=0, open_browser=True)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)
    print(f"Token saved to: {TOKEN_FILE}")

    print(f"\nNew refresh token: {creds.refresh_token}")
    print("\nUpdate your .env file with:")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")

    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.channels().list(part="snippet", mine=True)
    response = request.execute()
    items = response.get("items", [])
    if items:
        channel = items[0]
        print(f"\nAuthenticated as: {channel['snippet']['title']}")
    else:
        print("\nWARNING: No YouTube channel found. Create one at youtube.com.")

    print("\nNow test thumbnail upload with:")
    print("python -c \"from modules.youtube_uploader import get_authenticated_service; service = get_authenticated_service(); print('Auth OK')\"")


if __name__ == "__main__":
    re_authenticate()
