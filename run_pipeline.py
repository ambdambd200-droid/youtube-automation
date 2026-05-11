"""
Main pipeline - generates and uploads YouTube videos.
Zero paid APIs. Uses Groq (free), Coqui XTTS (free), Edge-TTS (free).
"""

import argparse, json, os, sys, asyncio, time, shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR, AUDIO_BACKGROUND

VOICEOVERS_DIR = os.path.join(OUTPUT_DIR, "voiceovers")

for d in [AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR, VOICEOVERS_DIR]:
    os.makedirs(d, exist_ok=True)


def run_pipeline(video_type="short", topic=None, voiceover_path=None):
    from modules.script_generator import generate_on_this_day_script, generate_long_script
    from modules.tts_generator import split_script_into_segments
    from modules.image_fetcher import fetch_and_download_images
    from modules.video_assembler import assemble_video
    from modules.thumbnail_generator import create_thumbnail
    from modules.youtube_uploader import upload_video, generate_seo_metadata
    from modules.audio_processor import enhance_tts, add_background_music
    from modules.voice_cloner import clone_voice_segments

    # Step 1: Script using free Groq API
    print(f"\n>>> STEP 1/5: Generating script with Groq (free Llama 3 70B)...")
    if video_type == "short":
        script_data = generate_on_this_day_script()
    else:
        script_data = generate_long_script(topic)

    script = script_data.get("script", "")
    script_clean = script_data.get("script_clean", script)
    title = script_data.get("topic", "Video")
    thumb_hint = script_data.get("thumbnail_hint", "")
    print(f"  Title: {title}")
    print(f"  Script: {len(script)} chars")
    if thumb_hint:
        print(f"  Thumbnail hint: {thumb_hint[:80]}")

    if not script or len(script) < 50:
        raise Exception(f"Script generation failed: {script[:200]}")

    # Step 2: Voiceover with cloning (user's voice if available)
    audio_path_used = None
    custom_voice = None

    # Find the user's custom voice file for cloning
    if voiceover_path and os.path.exists(voiceover_path):
        custom_voice = voiceover_path
    auto_voice = os.path.join(VOICEOVERS_DIR, "custom_voice.mp3")
    auto_voice2 = os.path.join(VOICEOVERS_DIR, "custom_voice.mp4")
    if os.path.exists(auto_voice):
        custom_voice = auto_voice
    if os.path.exists(auto_voice2):
        custom_voice = auto_voice2

    if custom_voice:
        print(f"\n>>> STEP 2/5: Cloning voice from {os.path.basename(custom_voice)}...")
        segments = split_script_into_segments(script_clean)
        print(f"  Segments: {len(segments)}")

        audio_files = clone_voice_segments(segments, custom_voice, prefix=video_type, language="en")

        if audio_files:
            # Combine audio segments
            combined_path = os.path.join(AUDIO_DIR, f"{video_type}_combined.mp3")
            if len(audio_files) > 1:
                import subprocess
                inputs = []
                for f in audio_files:
                    inputs.extend(["-i", f])
                filter_parts = [f"[{i}:0]" for i in range(len(audio_files))]
                filter_str = "".join(filter_parts) + f"concat=n={len(audio_files)}:v=0:a=1[out]"
                cmd = ["ffmpeg", *inputs, "-filter_complex", filter_str, "-map", "[out]", combined_path, "-y"]
                subprocess.run(cmd, capture_output=True)
                audio_path_used = combined_path if os.path.exists(combined_path) else audio_files[0]
            else:
                audio_path_used = audio_files[0]

    if not audio_path_used:
        # Fallback: Edge-TTS with enhancement
        print(f"\n>>> STEP 2/5: Using Edge-TTS (free)...")
        from modules.tts_generator import generate_tts as generate_tts_fn

        segments = split_script_into_segments(script_clean)
        print(f"  Segments: {len(segments)}")

        audio_files = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for i, seg in enumerate(segments):
            fname = f"{video_type}_voiceover_{i+1:02d}.mp3"
            path = os.path.join(AUDIO_DIR, fname)
            result = loop.run_until_complete(generate_tts_fn(seg, path))
            if result:
                audio_files.append(result)
                print(f"  Audio {i+1}: {os.path.getsize(result)} bytes")
        loop.close()

        if not audio_files:
            raise Exception("TTS generation failed")

        # Combine segments
        combined_path = os.path.join(AUDIO_DIR, f"{video_type}_combined.mp3")
        if len(audio_files) > 1:
            import subprocess
            inputs = []
            for f in audio_files:
                inputs.extend(["-i", f])
            filter_parts = [f"[{i}:0]" for i in range(len(audio_files))]
            filter_str = "".join(filter_parts) + f"concat=n={len(audio_files)}:v=0:a=1[out]"
            cmd = ["ffmpeg", *inputs, "-filter_complex", filter_str, "-map", "[out]", combined_path, "-y"]
            subprocess.run(cmd, capture_output=True)
            audio_path_used = combined_path if os.path.exists(combined_path) else audio_files[0]
        else:
            audio_path_used = audio_files[0]

    # Step 2b: Enhance audio (EQ, compression, background music)
    print(f"\n>>> STEP 2b/5: Enhancing audio...")
    enhanced = os.path.join(AUDIO_DIR, f"{video_type}_enhanced.mp3")
    bg = str(AUDIO_BACKGROUND) if AUDIO_BACKGROUND and os.path.exists(str(AUDIO_BACKGROUND)) else None
    enhance_tts(audio_path_used, enhanced)

    if bg:
        final_audio = os.path.join(AUDIO_DIR, f"{video_type}_final_audio.mp3")
        add_background_music(enhanced, bg, final_audio)
        audio_path_used = final_audio
    else:
        audio_path_used = enhanced

    if not audio_path_used or not os.path.exists(audio_path_used):
        raise Exception("Audio processing failed")

    # Step 3: Images
    print(f"\n>>> STEP 3/5: Fetching images...")
    img_count = 5 if video_type == "short" else 10
    img_result = fetch_and_download_images(query=title, count=img_count)
    images = img_result.get("files", [])
    print(f"  Images: {len(images)} files")

    # Step 4: Video
    print(f"\n>>> STEP 4/5: Assembling professional video...")
    video_path = assemble_video(
        images=images,
        audio_path=audio_path_used,
        output_path=os.path.join(VIDEOS_DIR, f"{video_type}_final.mp4"),
        background_music=bg,
        is_short=(video_type == "short"),
        text_overlays=[{"text": title, "start": 0, "end": 5}],
        script=script
    )
    if not video_path or not os.path.exists(video_path):
        raise Exception("Video assembly failed")
    print(f"  Video: {os.path.getsize(video_path)} bytes")

    # Step 5: Thumbnail
    print(f"\n>>> STEP 5/5: Generating thumbnail...")
    thumb_path = create_thumbnail(
        images, title,
        os.path.join(THUMBNAILS_DIR, f"{video_type}_thumb.jpg"),
        channel_logo_path="assets/channel_pic.png",
        channel_name="Depths"
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
    parser.add_argument("--voiceover", default=None, help="Custom voiceover file path")
    args = parser.parse_args()
    run_pipeline(args.type, args.topic, args.voiceover)
