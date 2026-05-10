"""
Main pipeline for GitHub Actions - generates + uploads YouTube videos.
Usage: python run_pipeline.py --type short
       python run_pipeline.py --type long --topic "Topic"
"""

import argparse, json, os, sys, asyncio, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR, AUDIO_BACKGROUND

for d in [AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR]:
    os.makedirs(d, exist_ok=True)

def step(name, fn, *args, **kwargs):
    print(f"\n{'='*60}")
    print(f"  [{name}]")
    print(f"{'='*60}")
    t0 = time.time()
    result = fn(*args, **kwargs)
    print(f"  Done in {time.time()-t0:.1f}s")
    return result

def run_pipeline(video_type="short", topic=None):
    from modules.script_generator import (generate_on_this_day_script, generate_long_script)
    from modules.tts_generator import generate_tts_from_text, split_script_into_segments
    from modules.image_fetcher import fetch_and_download_images
    from modules.video_assembler import assemble_video
    from modules.thumbnail_generator import create_thumbnail
    from modules.youtube_uploader import upload_video, generate_seo_metadata

    # Step 1: Script
    print(f"\n>>> STEP 1/5: Generating {'short' if video_type=='short' else 'long-form'} script...")
    if video_type == "short":
        script_data = generate_on_this_day_script()
    else:
        script_data = generate_long_script(topic)

    script = script_data.get("script", "")
    topic_text = script_data.get("topic", "Video")
    title = topic_text
    if script and "[" in script and "]" in script:
        t = script.split("[")[1].split("]")[0].strip()
        if t: title = t
    print(f"  Title: {title}")
    print(f"  Script: {len(script)} chars")

    if not script or len(script) < 50:
        raise Exception(f"Script generation failed: {script[:200]}")

    # Step 2: TTS
    print(f"\n>>> STEP 2/5: Generating voiceover...")
    segments = split_script_into_segments(script)
    print(f"  Segments: {len(segments)}")

    audio_files = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for i, seg in enumerate(segments):
        fname = f"{video_type}_voiceover.mp3"
        path = os.path.join(AUDIO_DIR, fname)
        result = loop.run_until_complete(generate_tts_from_text(seg, path))
        if result:
            audio_files.append(result)
            print(f"  Audio {i+1}: {os.path.getsize(result)} bytes")
    loop.close()

    if not audio_files:
        raise Exception("TTS generation failed")

    # Step 3: Images
    print(f"\n>>> STEP 3/5: Fetching images...")
    img_count = 5 if video_type == "short" else 10
    img_result = fetch_and_download_images(query=title, count=img_count)
    images = img_result.get("files", [])
    print(f"  Images: {len(images)} files")

    # Step 4: Video
    print(f"\n>>> STEP 4/5: Assembling video...")
    bg = str(AUDIO_BACKGROUND) if AUDIO_BACKGROUND and os.path.exists(str(AUDIO_BACKGROUND)) else None
    video_path = assemble_video(
        images=images,
        audio_path=audio_files[0],
        output_path=os.path.join(VIDEOS_DIR, f"{video_type}_final.mp4"),
        background_music=bg,
        is_short=(video_type == "short")
    )
    if not video_path or not os.path.exists(video_path):
        raise Exception("Video assembly failed")
    print(f"  Video: {os.path.getsize(video_path)} bytes")

    # Step 5: Thumbnail
    print(f"\n>>> STEP 5/5: Generating thumbnail...")
    thumb_path = create_thumbnail(
        images, title,
        os.path.join(THUMBNAILS_DIR, f"{video_type}_thumb.jpg")
    )
    # Upload to YouTube
    print(f"\n>>> UPLOADING to YouTube...")
    desc, tags = generate_seo_metadata(script, title)
    vid_id, resp = upload_video(
        video_path=video_path, title=title,
        description=desc, tags=tags,
        thumbnail_path=thumb_path
    )
    url = f"https://youtu.be/{vid_id}"
    print(f"\n{'='*60}")
    print(f"  SUCCESS! Video uploaded:")
    print(f"  Title: {title}")
    print(f"  URL: {url}")
    print(f"{'='*60}")
    return {"title": title, "url": url, "video_id": vid_id}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["short", "long"], required=True)
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()
    run_pipeline(args.type, args.topic)
