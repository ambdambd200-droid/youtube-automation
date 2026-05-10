"""
Uploads video to YouTube using YouTube Data API v3.
Call: python -m modules.youtube_uploader --video video.mp4 --title "Title" --description "Desc" --thumbnail thumb.jpg

NOTE: You need to set up YouTube OAuth 2.0 credentials first!
See: https://console.cloud.google.com/apis/credentials
"""

import argparse
import json
import os
import sys
import http.client
import urllib.parse
import mimetypes
import pickle
import re

sys.path.insert(0, ".")
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.pickle"
API_BASE = "www.googleapis.com"

def get_authenticated_service():
    """Get authenticated YouTube service using OAuth 2.0."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    # Try pickle file first
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If no pickle but we have all credentials in env, build from env
    if not creds and YOUTUBE_REFRESH_TOKEN and YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET:
        creds = Credentials(
            token=None,
            refresh_token=YOUTUBE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            scopes=SCOPES
        )

    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
                print(json.dumps({
                    "error": "YouTube credentials not configured. "
                             "Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env, "
                             "or run with --auth-flow to set up OAuth."
                }))
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

        # Save credentials for next run
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

def upload_video(video_path, title, description, tags, category_id="22", privacy_status="public", thumbnail_path=None):
    """Upload video to YouTube."""
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

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True,
                            mimetype="video/*")

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%", file=sys.stderr)

    video_id = response.get("id")

    # Upload thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
        except Exception as ex:
            print(f"Thumbnail upload error: {ex}", file=sys.stderr)

    return video_id, response

def generate_seo_metadata(script, title):
    """Generate SEO metadata for YouTube upload."""
    # Basic tags for Arabic dark explainer niche
    tags = [
        "شرح", "تاريخ", "حوادث", "dark history", "educational",
        "حقائق", "غموض", "وثائقي", "وثائقي قصير",
        "الشرح بالعربية", "معلومات عامة", "ثقافة"
    ]

    # Extract potential tags from title
    if title:
        title_words = title.replace("|", "").replace("-", "").split()
        tags.extend(title_words[:5])

    # Deduplicate
    tags = list(dict.fromkeys(tags))

    description = f"""{title}

📌 في هذا الفيديو:
{script[:2000] if script else ""}

━━━━━━━━━━━━━━━━━━━━━━
🔔 اشترك في القناة وفعل الجرس ليصلك كل جديد
👍 لا تنسى الإعجاب بالفيديو إذا أعجبك
💬 شاركنا رأيك في التعليقات
━━━━━━━━━━━━━━━━━━━━━━

#تاريخ #حوادث #شرح #معلومات #ثقافة #وثائقي
"""

    return description, tags

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=False, default="")
    parser.add_argument("--title", default="فيديو جديد")
    parser.add_argument("--description", default=None)
    parser.add_argument("--tags", nargs="+", default=[])
    parser.add_argument("--thumbnail", default=None)
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public")
    parser.add_argument("--script", default=None)
    parser.add_argument("--auth-flow", action="store_true",
                        help="Run OAuth flow to get YouTube credentials")
    args = parser.parse_args()

    if args.auth_flow:
        # Just run the auth flow without uploading
        get_authenticated_service()
        print(json.dumps({"status": "authenticated", "message": "YouTube OAuth setup complete!"}))
        return

    if not os.path.exists(args.video):
        result = {"error": f"Video file not found: {args.video}", "video_id": None}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    # Generate metadata if not provided
    description = args.description
    tags = list(args.tags)

    if not description or not tags:
        desc, gen_tags = generate_seo_metadata(args.script or "", args.title)
        if not description:
            description = desc
        if not tags:
            tags = gen_tags

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
