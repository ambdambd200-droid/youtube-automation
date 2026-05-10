"""
Assembles video from images + voiceover + background music using moviepy.
Call: python -m modules.video_assembler --images img1.jpg img2.jpg --audio voiceover.mp3 --output video.mp4 [--background music.mp3]
"""

import argparse
import json
import os
import sys
import random
import math

sys.path.insert(0, ".")
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, AUDIO_DIR

def get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        return "ffmpeg"

def assemble_video(images, audio_path, output_path, background_music=None, text_overlays=None, is_short=True):
    """Assemble video using moviepy with FFmpeg."""
    try:
        from moviepy import (
            VideoFileClip, AudioFileClip, ImageClip,
            CompositeVideoClip, concatenate_videoclips, TextClip,
            ColorClip
        )
    except ImportError:
        import json
        result = {"error": "moviepy not installed", "output": None}
        print(json.dumps(result, ensure_ascii=False))
        return None

    try:
        from PIL import Image as PILImage
        import numpy as np

        # Load audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        if not images or len(images) == 0:
            clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]
        else:
            img_duration = total_duration / len(images)
            clips = []

            for i, img_path in enumerate(images):
                if not os.path.exists(img_path):
                    continue
                try:
                    # Pre-resize image with Pillow for speed
                    pil_img = PILImage.open(img_path).convert("RGB")
                    pil_img.thumbnail((VIDEO_WIDTH, VIDEO_HEIGHT), PILImage.LANCZOS)
                    # Create a new image with the target size and paste centered
                    new_img = PILImage.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (20, 20, 30))
                    x = (VIDEO_WIDTH - pil_img.width) // 2
                    y = (VIDEO_HEIGHT - pil_img.height) // 2
                    new_img.paste(pil_img, (x, y))
                    frame = np.array(new_img)

                    clip = ImageClip(frame).with_duration(img_duration)
                    clips.append(clip)
                except Exception as ex:
                    print(f"Skipping image {img_path}: {ex}", file=sys.stderr)

            if not clips:
                clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]

        # Concatenate image clips
        video = concatenate_videoclips(clips, method="compose")

        # Set audio
        video = video.with_audio(audio)

        # Add background music if provided
        try:
            from moviepy import CompositeAudioClip
            from moviepy.audio.fx import AudioLoop, MultiplyVolume

            if background_music and os.path.exists(str(background_music)):
                bg_music = AudioFileClip(str(background_music))
                if bg_music.duration < total_duration:
                    bg_music = bg_music.with_effects([AudioLoop(duration=total_duration)])
                else:
                    bg_music = bg_music.subclipped(0, total_duration)
                bg_music = bg_music.with_effects([MultiplyVolume(0.15)])
                video = video.with_audio(CompositeAudioClip([audio, bg_music]))
        except Exception as ex:
            print(f"Background music error: {ex}", file=sys.stderr)

        # Write output
        video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=FPS,
            preset="medium",
            bitrate="4000k",
            ffmpeg_params=["-movflags", "+faststart"],
            logger=None
        )

        video.close()
        audio.close()

        return output_path

    except Exception as ex:
        print(f"Video assembly error: {ex}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", default=[])
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--background", default=None)
    parser.add_argument("--type", choices=["short", "long"], default="short")
    parser.add_argument("--title", default=None)

    # Accept JSON input via --json for complex data
    parser.add_argument("--json", default=None)

    args = parser.parse_args()

    images = args.images
    audio_path = args.audio
    output_path = args.output
    bg_music = args.background

    # Handle JSON input if provided
    if args.json:
        data = json.loads(args.json)
        images = data.get("images", images)
        audio_path = data.get("audio", audio_path)
        output_path = data.get("output", output_path)
        bg_music = data.get("background", bg_music)

    if not os.path.exists(audio_path):
        result = {"error": f"Audio file not found: {audio_path}", "output": None}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    video_path = assemble_video(images, audio_path, output_path, bg_music, is_short=(args.type == "short"))

    result = {
        "output": video_path,
        "images_used": len(images),
        "audio": audio_path
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
