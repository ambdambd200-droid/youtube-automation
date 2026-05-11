"""
Flask API server that wraps all YouTube automation modules.
n8n calls this server's endpoints via HTTP Request nodes.

Run: python api_server.py
Runs on: http://localhost:5001
"""

import json
import os
import sys
import uuid
import asyncio
from datetime import datetime

from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR
from modules.script_generator import generate_on_this_day_script, generate_long_script
from modules.tts_generator import generate_tts_from_text, split_script_into_segments
from modules.image_fetcher import fetch_and_download_images
from modules.video_assembler import assemble_video
from modules.thumbnail_generator import create_thumbnail

app = Flask(__name__)

# Ensure output dirs exist
for d in [AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, THUMBNAILS_DIR]:
    os.makedirs(d, exist_ok=True)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate-script", methods=["POST"])
def generate_script():
    data = request.get_json() or {}
    video_type = data.get("type", "short")
    date_str = data.get("date")

    try:
        if video_type == "short":
            result = generate_on_this_day_script(date_str)
        else:
            topic = data.get("topic")
            result = generate_long_script(topic)

        return jsonify(result)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/generate-tts", methods=["POST"])
def generate_tts():
    data = request.get_json() or {}
    script = data.get("script", "")
    output_prefix = data.get("output_prefix", f"vid_{uuid.uuid4().hex[:8]}")

    if not script:
        return jsonify({"error": "No script provided"}), 400

    try:
        segments = split_script_into_segments(script)
        os.makedirs(AUDIO_DIR, exist_ok=True)

        generated_files = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for i, seg in enumerate(segments):
            if len(segments) == 1:
                fname = f"{output_prefix}_voiceover.mp3"
            else:
                fname = f"{output_prefix}_voiceover_part{i+1:02d}.mp3"
            path = os.path.join(AUDIO_DIR, fname)
            result_path = loop.run_until_complete(generate_tts_from_text(seg, path))
            if result_path:
                generated_files.append(result_path)

        loop.close()

        return jsonify({
            "segments": len(generated_files),
            "files": generated_files,
            "script_length": len(script)
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/fetch-images", methods=["POST"])
def fetch_images():
    data = request.get_json() or {}
    query = data.get("query", "")
    script = data.get("script", "")
    count = data.get("count", 5)

    try:
        result = fetch_and_download_images(query, script, count)
        return jsonify(result)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/assemble-video", methods=["POST"])
def assemble_video_endpoint():
    data = request.get_json() or {}
    images = data.get("images", [])
    audio = data.get("audio", "")
    video_type = data.get("type", "short")
    bg_music = data.get("background", "")

    if not audio or not os.path.exists(str(audio)):
        return jsonify({"error": f"Audio file not found: {audio}"}), 400

    output_id = uuid.uuid4().hex[:8]
    output_path = os.path.join(VIDEOS_DIR, f"{video_type}_{output_id}.mp4")

    try:
        video_path = assemble_video(
            images=images,
            audio_path=audio,
            output_path=output_path,
            background_music=bg_music if bg_music else None,
            is_short=(video_type == "short")
        )
        return jsonify({
            "output": video_path,
            "images_used": len(images),
            "audio": audio
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/generate-thumbnail", methods=["POST"])
def generate_thumbnail_endpoint():
    data = request.get_json() or {}
    images = data.get("images", [])
    title = data.get("title", "New Video")

    output_id = uuid.uuid4().hex[:8]
    output_path = os.path.join(THUMBNAILS_DIR, f"thumb_{output_id}.jpg")

    try:
        result_path = create_thumbnail(images, title, output_path)
        return jsonify({
            "output": result_path,
            "title": title
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 5001))
    print(f"Starting YouTube Automation API on port {port}...")
    app.run(host="127.0.0.1", port=port, debug=False)
