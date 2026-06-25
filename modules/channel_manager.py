"""
Channel Manager — updates YouTube channel branding (caption/description, profile pic, banner).
Handles the auto-transition when the World Cup ends.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    get_channel_description, is_world_cup_active,
    LOG_DIR, OUTPUT_DIR,
)


def get_authenticated_youtube():
    """Get authenticated YouTube service."""
    from modules.youtube_uploader import get_authenticated_service
    return get_authenticated_service()


def _log_channel_update(action, status, details=None):
    """Log a channel update action."""
    from datetime import datetime
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "status": status,
        "details": details or {},
    }
    log_dir = os.path.join(LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "channel_updates.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def get_channel_info():
    """Fetch current YouTube channel information.

    Returns:
        Dict with channel info (title, description, id), or None on failure.
    """
    try:
        youtube = get_authenticated_youtube()
        request = youtube.channels().list(part="snippet,brandingSettings", mine=True)
        response = request.execute()
        items = response.get("items", [])
        if items:
            channel = items[0]
            snippet = channel.get("snippet", {})
            branding = channel.get("brandingSettings", {}).get("channel", {})
            return {
                "id": channel.get("id"),
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "country": snippet.get("country"),
                "custom_url": snippet.get("customUrl"),
                "keywords": branding.get("keywords", ""),
            }
        return None
    except Exception as e:
        print(f"  [channel_manager] Error fetching channel info: {e}", flush=True)
        return None


def update_channel_description():
    """Update the channel description based on whether the World Cup is active.

    When the World Cup ends, the channel description is automatically updated
    to remove World Cup references.

    The YouTube API rejects `part=snippet` for `channels.update()` (ERROR_PART_UNEXPECTED).
    Instead, `part=brandingSettings` with a `channel.description` field works.

    Returns:
        True if updated, False otherwise.
    """
    try:
        youtube = get_authenticated_youtube()
        new_description = get_channel_description()

        # Fetch current description to check if already up to date
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
        items = response.get("items", [])
        if not items:
            print("  [channel_manager] Could not fetch channel info", flush=True)
            return False

        channel = items[0]
        channel_id = channel["id"]
        current_desc = channel.get("snippet", {}).get("description", "")

        if current_desc == new_description:
            print(f"  [channel_manager] Channel description already up to date", flush=True)
            return True

        # Update via brandingSettings — the only part the API accepts for channel updates.
        youtube.channels().update(
            part="brandingSettings",
            body={
                "id": channel_id,
                "brandingSettings": {
                    "channel": {
                        "description": new_description,
                    }
                },
            },
        ).execute()

        wc_status = "active" if is_world_cup_active() else "ended"
        print(f"  [channel_manager] Channel description updated (World Cup: {wc_status})", flush=True)
        _log_channel_update("update_description", "success", {
            "world_cup_status": wc_status,
        })
        return True

    except Exception as e:
        print(f"  [channel_manager] Error updating description: {e}", flush=True)
        _log_channel_update("update_description", "failed", {"error": str(e)})
        return False


def upload_channel_branding(profile_picture_path=None, banner_path=None):
    """Upload profile picture and/or banner to YouTube channel.

    Args:
        profile_picture_path: Path to profile picture image, or None to skip.
        banner_path: Path to banner image, or None to skip.

    Returns:
        Dict with results.
    """
    results = {"profile_picture": False, "banner": False}

    try:
        youtube = get_authenticated_youtube()
        channel_info = get_channel_info()
        if not channel_info:
            print("  [channel_manager] Could not fetch channel info", flush=True)
            return results

        channel_id = channel_info["id"]

        # Upload profile picture
        if profile_picture_path and os.path.exists(profile_picture_path):
            # The YouTube Data API v3 library (google-api-python-client) does not
            # support media uploads via channels().update(media_body=...).
            # Additionally, part="snippet" is rejected by the API (ERROR_PART_UNEXPECTED).
            # Profile pictures must be uploaded manually via YouTube Studio.
            print(f"  [channel_manager] Profile picture API upload not supported by this library version.", flush=True)
            print(f"  [channel_manager] Upload manually: https://studio.youtube.com -> Customization -> Branding", flush=True)
            _log_channel_update("upload_profile_pic", "skipped", {"reason": "media_body not supported by library"})

        # Upload banner
        if banner_path and os.path.exists(banner_path):
            try:
                from googleapiclient.http import MediaFileUpload
                youtube.channelBanners().insert(
                    channelId=channel_id,
                    media_body=MediaFileUpload(banner_path, mimetype="image/png"),
                ).execute()
                print(f"  [channel_manager] Channel banner updated", flush=True)
                results["banner"] = True
                _log_channel_update("upload_banner", "success")
            except Exception as e:
                print(f"  [channel_manager] Banner upload error: {e}", flush=True)
                _log_channel_update("upload_banner", "failed", {"error": str(e)})

    except Exception as e:
        print(f"  [channel_manager] Error: {e}", flush=True)

    return results


def check_and_update_channel():
    """Check World Cup status and update channel branding if needed.

    This is the main entry point called by the pipeline.
    - If World Cup just ended: update description, upload new branding
    - If World Cup still active: ensure WC description is set
    - If World Cup ended long ago: ensure post-WC description is set

    Gracefully handles missing YouTube credentials — will skip API calls
    and only generate local files if auth isn't available.

    Returns:
        Dict with actions taken.
    """
    result = {
        "world_cup_active": is_world_cup_active(),
        "description_updated": False,
        "branding_uploaded": False,
    }

    print(f"\n>>> Checking channel branding (World Cup: {'ACTIVE' if is_world_cup_active() else 'ENDED'})...", flush=True)

    # Check if YouTube credentials are available before attempting API calls
    from config import YOUTUBE_CLIENT_ID, YOUTUBE_REFRESH_TOKEN
    has_creds = bool(YOUTUBE_CLIENT_ID and YOUTUBE_REFRESH_TOKEN)

    if not has_creds:
        print(f"  [channel_manager] YouTube credentials not configured — skipping channel API calls", flush=True)
        result["description_updated"] = False
        result["branding_uploaded"] = False
    else:
        # 1. Update description via API
        desc_updated = update_channel_description()
        result["description_updated"] = desc_updated

        # 2. Upload branding assets via API
        from modules.channel_branding_generator import generate_all_branding
        branding_dir = os.path.join(OUTPUT_DIR, "channel_art")
        profile_pic = os.path.join(branding_dir, "profile_picture.png")
        banner = os.path.join(branding_dir, "channel_banner.png")

        if not os.path.exists(profile_pic) or not os.path.exists(banner):
            branding = generate_all_branding()
            profile_pic = branding.get("profile_picture")
            banner = branding.get("banner")

        if os.path.exists(profile_pic) and os.path.exists(banner):
            upload_result = upload_channel_branding(
                profile_picture_path=profile_pic if os.path.exists(profile_pic) else None,
                banner_path=banner if os.path.exists(banner) else None,
            )
            result["branding_uploaded"] = upload_result.get("profile_picture") or upload_result.get("banner")

    # Also run the channel branding generator locally if images don't exist
    from modules.channel_branding_generator import generate_all_branding
    branding_dir = os.path.join(OUTPUT_DIR, "channel_art")
    if not os.path.exists(os.path.join(branding_dir, "profile_picture.png")):
        print(f"  [channel_manager] Generating local channel branding assets...", flush=True)
        generate_all_branding()

    wc_status = "active" if is_world_cup_active() else "ended"
    print(f"  [channel_manager] Channel check complete (World Cup: {wc_status})", flush=True)

    return result


if __name__ == "__main__":
    result = check_and_update_channel()
    print(json.dumps(result, indent=2, default=str))
