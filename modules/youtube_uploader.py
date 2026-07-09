"""
Uploads video to YouTube using YouTube Data API v3.
"""

import argparse
import json
import os
import sys
import pickle
import socket
import time

sys.path.insert(0, ".")
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = "youtube_token.pickle"
UPLOAD_TIMEOUT = 600  # 10-minute socket timeout for uploads

def _is_ci():
    """Detect if running in CI (GitHub Actions, etc)."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"

def _build_youtube(creds):
    """Build youtube service with high timeout."""
    import httplib2
    http = httplib2.Http(timeout=UPLOAD_TIMEOUT)
    http = creds.authorize(http)
    from googleapiclient.discovery import build
    return build("youtube", "v3", http=http)


def get_authenticated_service():
    """Get authenticated YouTube service using OAuth 2.0.
    Tries: env vars (client_id+secret+refresh) → pickle file → (local only) interactive OAuth."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    socket.setdefaulttimeout(UPLOAD_TIMEOUT)
    errors = []

    # Attempt 1: Build from env vars
    if YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN:
        try:
            creds = Credentials(
                token=None,
                refresh_token=YOUTUBE_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=YOUTUBE_CLIENT_ID,
                client_secret=YOUTUBE_CLIENT_SECRET,
                scopes=SCOPES
            )
            if creds.refresh_token:
                creds.refresh(Request())
            if creds and creds.valid:
                return _build_youtube(creds)
        except Exception as e:
            errors.append(f"env: {e}")

    # Attempt 2: Pickle file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)
            if creds:
                if creds.refresh_token:
                    creds.refresh(Request())
                if creds and creds.valid:
                    return _build_youtube(creds)
        except Exception as e:
            errors.append(f"pickle: {e}")

    # All attempts failed
    err_msg = "YouTube auth failed. " + "; ".join(errors)
    if _is_ci():
        err_msg += ". Set secrets in repo: Settings → Secrets and variables → Actions: "
        err_msg += "YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_TOKEN_B64"
        print(json.dumps({"error": err_msg}))
        raise RuntimeError(err_msg)

    # Local interactive fallback
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print(json.dumps({"error": "YouTube credentials not configured in .env"}))
        sys.exit(1)

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
            }
        },
        SCOPES
    )
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "wb") as token:
        pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

def verify_auth():
    """Verify authentication by fetching channel info."""
    youtube = get_authenticated_service()
    request = youtube.channels().list(part="snippet", mine=True)
    response = request.execute()
    items = response.get("items", [])
    if items:
        channel = items[0]
        print(json.dumps({
            "status": "ok",
            "channel_name": channel["snippet"]["title"],
            "channel_id": channel["id"]
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "error",
            "error": "No YouTube channel found. Create one at youtube.com."
        }))
    return items

def upload_video(video_path, title, description, tags, category_id="22", privacy_status="public", thumbnail_path=None):
    """Upload video to YouTube with retry logic for timeout errors."""
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print(json.dumps({
            "error": "google-api-python-client not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        }))
        sys.exit(1)

    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    file_size = os.path.getsize(video_path)
    print(f"  Upload starting: {file_size / 1024 / 1024:.1f} MB, 50MB chunks", flush=True)
    chunk_size = 50 * 1024 * 1024

    media = MediaFileUpload(video_path, chunksize=chunk_size, resumable=True,
                            mimetype="video/*")

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    max_retries = 5
    attempt = 0

    while response is None and attempt <= max_retries:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  Upload progress: {int(status.progress() * 100)}%", flush=True)
        except Exception as e:
            attempt += 1
            err_str = str(e).lower()
            is_timeout = any(t in err_str for t in ["timeout", "timed out", "deadline", "reset"])
            if attempt > max_retries or not is_timeout:
                raise
            wait = min(30 * attempt, 120)
            print(f"  Upload timeout (attempt {attempt}/{max_retries}), retrying in {wait}s...", flush=True)
            time.sleep(wait)
            media = MediaFileUpload(video_path, chunksize=chunk_size, resumable=True, mimetype="video/*")
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

    if response is None:
        raise RuntimeError("Upload failed after all retries")

    video_id = response.get("id")

    # Upload thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
        except Exception:
            print(f"  [SKIP] Custom thumbnail not available yet (upload manually on YouTube Studio)", file=sys.stderr)

    return video_id, response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=False, default="")
    parser.add_argument("--title", default="New Video")
    parser.add_argument("--description", default=None)
    parser.add_argument("--tags", nargs="+", default=[])
    parser.add_argument("--thumbnail", default=None)
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public")
    parser.add_argument("--auth-flow", action="store_true",
                        help="Run OAuth flow to get YouTube credentials")
    parser.add_argument("--verify", action="store_true",
                        help="Verify authentication without uploading")
    args = parser.parse_args()

    if args.verify:
        verify_auth()
        return

    if args.auth_flow:
        get_authenticated_service()
        print(json.dumps({"status": "authenticated", "message": "YouTube OAuth setup complete!"}))
        return

    if not os.path.exists(args.video):
        result = {"error": f"Video file not found: {args.video}", "video_id": None}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    description = args.description
    tags = list(args.tags)

    if not description or not tags:
        from modules.seo_generator import generate_metadata
        seo = generate_metadata(args.title, "movie")
        if not description:
            description = seo["description"]
        if not tags:
            tags = seo["tags"]

    video_id, response = upload_video(
        args.video,
        args.title,
        description,
        tags,
        thumbnail_path=args.thumbnail
    )

    result = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": args.title
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()