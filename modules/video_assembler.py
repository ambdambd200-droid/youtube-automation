"""
Professional video assembler with Ken Burns zoom, crossfade, text overlays.
"""

import argparse
import json
import os
import sys
import math
import random

sys.path.insert(0, ".")
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS


def make_text_clip(text, duration, font_size=50, position="bottom"):
    """Create a text overlay clip using PIL and numpy."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        overlay_height = 120
        img = Image.new("RGBA", (VIDEO_WIDTH, overlay_height), (0, 0, 0, 160))

        draw = ImageDraw.Draw(img)

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\tahoma.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            None
        ]:
            try:
                font = ImageFont.truetype(fp, font_size) if fp else ImageFont.load_default()
                break
            except:
                continue

        lines = []
        words = text.split()
        current = ""
        for w in words:
            test = current + " " + w if current else w
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] < VIDEO_WIDTH - 80:
                current = test
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)

        y_pos = 10
        for line in lines[:3]:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            x = (VIDEO_WIDTH - w) // 2
            draw.text((x + 2, y_pos + 2), line, fill=(0, 0, 0), font=font)
            draw.text((x, y_pos), line, fill=(255, 255, 255), font=font)
            y_pos += font_size + 10

        from moviepy import ImageClip
        frame = np.array(img)
        clip = ImageClip(frame).with_duration(duration).with_position(("center", "bottom"))
        return clip
    except Exception as ex:
        print(f"Text clip error: {ex}", file=sys.stderr)
        return None


def assemble_video(images, audio_path, output_path, background_music=None,
                   text_overlays=None, is_short=True, title=None, script=None):
    """Assemble video with Ken Burns zoom, crossfade, and text."""
    try:
        from moviepy import (
            AudioFileClip, ImageClip,
            CompositeVideoClip, concatenate_videoclips,
            ColorClip, VideoClip
        )
    except ImportError:
        print(json.dumps({"error": "moviepy not installed", "output": None}))
        return None

    try:
        from PIL import Image as PILImage
        import numpy as np
        from moviepy.video.fx import Resize
        from moviepy.audio.fx import AudioLoop, MultiplyVolume
        from moviepy import CompositeAudioClip

        # Load audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        print(f"  [assembler] Audio: {total_duration:.1f}s", flush=True)

        if not images or len(images) == 0:
            clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]
        else:
            img_duration = total_duration / len(images)
            clips = []

            for i, img_path in enumerate(images):
                if not os.path.exists(img_path):
                    continue
                try:
                    pil_img = PILImage.open(img_path).convert("RGB")
                    w, h = pil_img.size
                    scale = max(VIDEO_WIDTH / w, VIDEO_HEIGHT / h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    pil_img = pil_img.resize((new_w, new_h), PILImage.LANCZOS)

                    x = (new_w - VIDEO_WIDTH) // 2
                    y = (new_h - VIDEO_HEIGHT) // 2
                    pil_img = pil_img.crop((x, y, x + VIDEO_WIDTH, y + VIDEO_HEIGHT))

                    frame = np.array(pil_img)
                    base_clip = ImageClip(frame).with_duration(img_duration)

                    # Ken Burns zoom (slow zoom in)
                    zoom_max = 1.12 if is_short else 1.08
                    zoomed = base_clip.with_effects([
                        Resize(lambda t: 1 + (zoom_max - 1) * (t / max(img_duration, 0.01)))
                    ])

                    clips.append(zoomed)
                except Exception as ex:
                    print(f"Skipping image {img_path}: {ex}", file=sys.stderr)

            if not clips:
                clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(total_duration)]

        print(f"  [assembler] Created {len(clips)} image clips with Ken Burns", flush=True)

        # Crossfade between clips
        final_clips = []
        for i, clip in enumerate(clips):
            if i > 0:
                from moviepy.video.fx import CrossFadeIn
                clip = clip.with_effects([CrossFadeIn(0.3)])
            final_clips.append(clip)

        video = concatenate_videoclips(final_clips, method="compose")
        video = video.with_audio(audio)

        # Background music
        try:
            if background_music and os.path.exists(str(background_music)):
                bg_music = AudioFileClip(str(background_music))
                if bg_music.duration < total_duration:
                    bg_music = bg_music.with_effects([AudioLoop(duration=total_duration)])
                else:
                    bg_music = bg_music.subclipped(0, total_duration)
                bg_music = bg_music.with_effects([MultiplyVolume(0.12)])
                video = video.with_audio(CompositeAudioClip([audio, bg_music]))
        except Exception as ex:
            print(f"Background music error: {ex}", file=sys.stderr)

        print(f"  [assembler] Adding overlays...", flush=True)

        # Text overlays
        overlay_clips = [video]

        if text_overlays:
            for to in text_overlays:
                txt = to.get("text", "")
                start = to.get("start", 0)
                end = to.get("end", total_duration)
                dur = min(end - start, total_duration - start)
                if dur > 0.5 and txt:
                    tc = make_text_clip(txt, dur)
                    if tc:
                        overlay_clips.append(tc)

        # Add text at beginning (title)
        if title:
            title_clip = make_text_clip(title, min(5, total_duration), font_size=55)
            if title_clip:
                overlay_clips.append(title_clip)

        # Add 2-3 key captions only (not every word)
        if script and len(overlay_clips) < 5:
            sentences = [s.strip() for s in script.replace('؟', '?').replace('،', ',').split('.') if len(s.strip()) > 15]
            caption_count = min(3, len(sentences))
            caption_duration = total_duration / max(caption_count, 1)
            for idx in range(caption_count):
                start_t = idx * caption_duration
                cap_text = sentences[idx][:80]
                tc = make_text_clip(cap_text, min(caption_duration, total_duration - start_t), font_size=40)
                if tc:
                    tc = tc.with_start(start_t)
                    overlay_clips.append(tc)

        if len(overlay_clips) > 1:
            video = CompositeVideoClip(overlay_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        print(f"  [assembler] Rendering video...", flush=True)

        # Shorts: keep landscape 1920x1080 (YT accepts both)
        # Use fast preset for reasonable speed
        video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=FPS,
            preset="veryfast",
            bitrate="3000k",
            ffmpeg_params=["-movflags", "+faststart"],
            logger=None
        )

        video.close()
        audio.close()
        return output_path

    except Exception as ex:
        print(f"Video assembly error: {ex}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", default=[])
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--background", default=None)
    parser.add_argument("--type", choices=["short", "long"], default="short")
    parser.add_argument("--title", default=None)
    parser.add_argument("--script", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    images = args.images
    audio_path = args.audio
    output_path = args.output
    bg_music = args.background
    vid_title = args.title
    script_text = args.script

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

    video_path = assemble_video(
        images, audio_path, output_path, bg_music,
        is_short=(args.type == "short"),
        title=vid_title,
        script=script_text
    )

    result = {"output": video_path, "images_used": len(images), "audio": audio_path}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()