"""
Main pipeline orchestrator for GitHub Actions.
Runs the full video generation pipeline and uploads to YouTube.

Usage:
  python run_pipeline.py --type short
  python run_pipeline.py --type long --topic "Custom topic"
"""

import argparse
import json
import os
import sys
import asyncio
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR, AUDIO_BACKGROUND

# Ensure dirs exist
for d in [AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR]:
    os.makedirs(d, exist_ok=True)


def step(name, fn, *args, **kwargs):
    """Run a step with logging."""
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"{'='*60}")
    result = fn(*args, **kwargs)
    status = "OK" if result and not result.get("error") else "FAILED"
    print(f"  -> {status}")
    return result


def run_short_pipeline():
    """Run the full daily short video pipeline."""
    from modules.script_generator import generate_on_this_day_script
    from modules.tts_generator import generate_tts_from_text, split_script_into_segments
    from modules.image_fetcher import fetch_and_download_images
    from modules.video_assembler import assemble_video
    from modules.thumbnail_generator import create_thumbnail
    from modules.youtube_uploader import upload_video, generate_seo_metadata

    # Step 1: Generate script
    script_data = step("Generate Script", generate_on_this_day_script)
    if script_data.get("error"):
        raise Exception(f"Script generation failed: {script_data['error']}")

    script = script_data.get("script", "")
    topic = script_data.get("topic", "Historical event")
    title = topic
    if script and "[" in script and "]" in script:
        title = script.split("[")[1].split("]")[0].strip()

    print(f"\n  Title: {title}")
    print(f"  Script: {len(script)} chars")

    # Step 2: Generate TTS
    segments = split_script_into_segments(script)
    print(f"\n  TTS Segments: {len(segments)}")

    audio_files = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for i, seg in enumerate(segments):
        fname = "short_voiceover.mp3" if len(segments) == 1 else f"short_voiceover_part{i+1:02d}.mp3"
        path = os.path.join(AUDIO_DIR, fname)
        result = loop.run_until_complete(generate_tts_from_text(seg, path))
        if result:
            audio_files.append(result)
            print(f"  Audio {i+1}: {result} ({os.path.getsize(result)} bytes)")

    loop.close()

    if not audio_files:
        raise Exception("TTS generation failed")

    # Step 3: Fetch images
    img_result = step("Fetch Images", fetch_and_download_images, query=topic, script=script, count=5)
    images = img_result.get("files", [])
    print(f"  Images: {len(images)} files")

    # Step 4: Assemble video
    bg = AUDIO_BACKGROUND if os.path.exists(str(AUDIO_BACKGROUND)) else None
    video_path = step("Assemble Video", assemble_video,
                      images=images,
                      audio_path=audio_files[0],
                      output_path=os.path.join(VIDEOS_DIR, "short_final.mp4"),
                      background_music=bg,
                      is_short=True)

    if not video_path or not os.path.exists(video_path):
        raise Exception("Video assembly failed")
    print(f"  Video: {video_path} ({os.path.getsize(video_path)} bytes)")

    # Step 5: Generate thumbnail
    thumb_path = step("Generate Thumbnail", create_thumbnail,
                      images=images,
                      title=title,
                      output_path=os.path.join(THUMBNAILS_DIR, "short_thumb.jpg"))
    print(f"  Thumbnail: {thumb_path}")

    # Step 6: Upload to YouTube
    desc, tags = generate_seo_metadata(script, title)
    upload_result = step("Upload to YouTube", upload_video,
                         video_path=video_path,
                         title=title,
                         description=desc,
                         tags=tags,
                         thumbnail_path=thumb_path)

    return {
        "title": title,
        "video_path": video_path,
        "video_url": f"https://youtu.be/{upload_result[0]}" if upload_result else None
    }


def run_long_pipeline(topic=None):
    """Run the full weekly long-form video pipeline."""
    from modules.script_generator import generate_long_script
    from modules.tts_generator import generate_tts_from_text, split_script_into_segments
    from modules.image_fetcher import fetch_and_download_images
    from modules.video_assembler import assemble_video
    from modules.thumbnail_generator import create_thumbnail
    from modules.youtube_uploader import upload_video, generate_seo_metadata

    # Step 1: Generate script
    script_data = step("Generate Long Script", generate_long_script, topic=topic)
    if script_data.get("error"):
        raise Exception(f"Script generation failed: {script_data['error']}")

    script = script_data.get("script", "")
    topic_title = script_data.get("topic", topic or "Deep dive")

    title = topic_title
    if script and "[" in script and "]" in script:
        title = script.split("[")[1].split("]")[0].strip()

    print(f"\n  Title: {title}")
    print(f"  Script: {len(script)} chars")

    # Step 2: Generate TTS (multi-segment for long script)
    segments = split_script_into_segments(script)
    print(f"\n  TTS Segments: {len(segments)}")

    audio_files = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for i, seg in enumerate(segments):
        fname = f"long_voiceover_part{i+1:02d}.mp3"
        path = os.path.join(AUDIO_DIR, fname)
        result = loop.run_until_complete(generate_tts_from_text(seg, path))
        if result:
            audio_files.append(result)

    loop.close()

    if not audio_files:
        raise Exception("TTS generation failed")

    # Step 3: Fetch images
    img_result = step("Fetch Images", fetch_and_download_images, query=topic_title, count=10)
    images = img_result.get("files", [])
    print(f"  Images: {len(images)} files")

    # Step 4: Assemble video
    bg = AUDIO_BACKGROUND if os.path.exists(str(AUDIO_BACKGROUND)) else None
    video_path = step("Assemble Video", assemble_video,
                      images=images,
                      audio_path=audio_files[0],
                      output_path=os.path.join(VIDEOS_DIR, "long_final.mp4"),
                      background_music=bg,
                      is_short=False)

    if not video_path or not os.path.exists(video_path):
        raise Exception("Video assembly failed")
    print(f"  Video: {video_path} ({os.path.getsize(video_path)} bytes)")

    # Step 5: Generate thumbnail
    thumb_path = step("Generate Thumbnail", create_thumbnail,
                      images=images,
                      title=title,
                      output_path=os.path.join(THUMBNAILS_DIR, "long_thumb.jpg"))
    print(f"  Thumbnail: {thumb_path}")

    # Step 6: Upload to YouTube
    desc, tags = generate_seo_metadata(script, title)
    upload_result = step("Upload to YouTube", upload_video,
                         video_path=video_path,
                         title=title,
                         description=desc,
                         tags=tags,
                         thumbnail_path=thumb_path)

    return {
        "title": title,
        "video_path": video_path,
        "video_url": f"https://youtu.be/{upload_result[0]}" if upload_result else None
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["short", "long"], required=True)
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()

    print("YouTube Automation Pipeline")
    print(f"Type: {args.type}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"CWD: {os.getcwd()}")

    try:
        if args.type == "short":
            result = run_short_pipeline()
        else:
            result = run_long_pipeline(args.topic)

        print(f"\n{'='*60}")
        print(f"  SUCCESS!")
        print(f"  Title: {result.get('title')}")
        print(f"  URL: {result.get('video_url', 'N/A')}")
        print(f"{'='*60}")

    except Exception as ex:
        print(f"\n{'='*60}")
        print(f"  FAILED: {ex}")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
