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
        # Load audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        if not images or len(images) == 0:
            # Create a solid color background
            clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]
        else:
            # Split audio duration among images
            img_duration = total_duration / len(images)
            clips = []

            for i, img_path in enumerate(images):
                if not os.path.exists(img_path):
                    continue
                try:
                    clip = (ImageClip(img_path)
                            .with_duration(img_duration)
                            .resized(width=VIDEO_WIDTH))
                    # Center crop if needed
                    if clip.h < VIDEO_HEIGHT:
                        clip = clip.resized(height=VIDEO_HEIGHT)
                    clip = clip.cropped(x_center=clip.w/2, y_center=clip.h/2,
                                        width=VIDEO_WIDTH, height=VIDEO_HEIGHT)
                    clips.append(clip)
                except Exception as ex:
                    print(f"Skipping image {img_path}: {ex}", file=sys.stderr)

            if not clips:
                clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]

        # Concatenate image clips
        video = concatenate_videoclips(clips, method="compose")

        # Set audio
        video = video.with_audio(audio)

        # Add background music if provided, otherwise generate subtle ambient
        try:
            from moviepy import CompositeAudioClip

            if background_music and os.path.exists(str(background_music)):
                try:
                    bg_music = AudioFileClip(str(background_music))
                    if bg_music.duration < total_duration:
                        bg_music = bg_music.loop(duration=total_duration)
                    else:
                        bg_music = bg_music.subclipped(0, total_duration)
                    bg_music = bg_music.with_effects([(lambda v: v * 0.15)])
                except Exception as ex:
                    print(f"Background music error: {ex}", file=sys.stderr)
                    bg_music = None
            else:
                bg_music = None

            if bg_music is not None:
                video = video.with_audio(CompositeAudioClip([audio, bg_music]))
            # else: keep just the voiceover audio
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
