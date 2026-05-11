"""
Professional video assembler with dynamic motion, transitions, and text animations.
No external paid services - pure MoviePy + ffmpeg.
"""

import argparse
import json
import os
import sys
import random
import math

sys.path.insert(0, ".")
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS


def ease_in_out(t):
    """Smooth ease-in-out curve for Ken Burns."""
    return t * t * (3 - 2 * t)


def make_animated_text(text, duration, font_size=52, anim_type="slide_up"):
    """
    Create animated text overlay with professional motion.
    Types: slide_up, typewriter, fade_in, scale_in
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import VideoClip

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            None
        ]:
            try:
                font = ImageFont.truetype(fp, font_size) if fp else ImageFont.load_default()
                break
            except:
                continue

        # Wrap text
        draw_test = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = text.split()
        lines = []
        current = ""
        for w in words:
            test = current + " " + w if current else w
            bbox = draw_test.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] < VIDEO_WIDTH - 160:
                current = test
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        lines = lines[:3]

        line_height = font_size + 15
        total_h = len(lines) * line_height + 40
        bar_h = total_h + 20

        def make_frame(t):
            progress = min(t / max(duration, 0.01), 1)

            # Animation offset
            offset = 0
            alpha = 1
            if anim_type == "slide_up":
                offset = int(80 * (1 - ease_in_out(min(progress * 2, 1))))
                alpha = min(progress * 4, 1)
            elif anim_type == "fade_in":
                alpha = min(progress * 3, 1)
            elif anim_type == "scale_in":
                scale = 0.5 + 0.5 * ease_in_out(min(progress * 2, 1))
                alpha = min(progress * 3, 1)

            # Create frame with background bar
            bar = Image.new("RGBA", (VIDEO_WIDTH, bar_h), (0, 0, 0, int(160 * alpha)))
            draw = ImageDraw.Draw(bar)

            y_start = 20 + offset
            for li, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
                x = (VIDEO_WIDTH - w) // 2
                y = y_start + li * line_height

                # Shadow
                for ox, oy in [(3, 3), (2, 2)]:
                    draw.text((x + ox, y + oy), line, fill=(0, 0, 0, int(200 * alpha)), font=font)
                # Main text
                draw.text((x, y), line, fill=(255, 255, 255, int(255 * alpha)), font=font)

            frame = np.array(bar)
            return frame

        clip = VideoClip(make_frame, duration=duration).with_position(("center", "bottom"))
        return clip

    except Exception as ex:
        print(f"  [assembler] Text animation error: {ex}", flush=True)
        return None


def make_title_animation(text, duration):
    """Create animated title that scales and fades in at center."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import VideoClip

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            None
        ]:
            try:
                font = ImageFont.truetype(fp, 60) if fp else ImageFont.load_default()
                break
            except:
                continue

        # Wrap
        draw_test = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = text.split()
        lines = []
        current = ""
        for w in words:
            test = current + " " + w if current else w
            bbox = draw_test.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] < VIDEO_WIDTH - 200:
                current = test
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        lines = lines[:2]

        line_h = 70

        def make_frame(t):
            progress = min(t / max(duration, 0.01), 1)
            p = ease_in_out(min(progress * 2, 1))
            alpha = min(progress * 3, 1)
            scale = 0.3 + 0.7 * p

            frame_w = int(VIDEO_WIDTH * scale)
            frame_h = int((len(lines) * line_h + 40) * scale)

            # Draw on scaled canvas then place
            canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
            overlay = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, int(180 * alpha)))
            draw = ImageDraw.Draw(overlay)

            for li, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
                x = (frame_w - w) // 2
                y = 20 + li * line_h

                for ox, oy in [(3, 3), (2, 2)]:
                    draw.text((x + ox, y + oy), line, fill=(0, 0, 0, int(200 * alpha)), font=font)
                draw.text((x, y), line, fill=(255, 215, 0, int(255 * alpha)), font=font)

            canvas.paste(overlay, ((VIDEO_WIDTH - frame_w) // 2, (VIDEO_HEIGHT - frame_h) // 2))
            return np.array(canvas)

        return VideoClip(make_frame, duration=duration)

    except Exception as ex:
        print(f"  [assembler] Title animation error: {ex}", flush=True)
        return None


def assemble_video(images, audio_path, output_path, background_music=None,
                   text_overlays=None, is_short=True, title=None, script=None):
    """Assemble professional video with motion, transitions, and audio."""
    try:
        from moviepy import (
            AudioFileClip, ImageClip, VideoClip,
            CompositeVideoClip, concatenate_videoclips,
            ColorClip
        )
        from PIL import Image as PILImage
        import numpy as np
        from moviepy.video.fx import Resize, CrossFadeIn, FadeIn, FadeOut
        from moviepy.audio.fx import AudioLoop, MultiplyVolume
        from moviepy import CompositeAudioClip
        from modules.audio_processor import enhance_tts, add_background_music

        # Load and enhance audio
        print(f"  [assembler] Processing audio...", flush=True)
        enhanced_audio = os.path.join(os.path.dirname(output_path), "enhanced_audio.mp3")
        enhance_tts(audio_path, enhanced_audio)

        final_audio = os.path.join(os.path.dirname(output_path), "final_audio.mp3")
        if background_music and os.path.exists(str(background_music)):
            add_background_music(enhanced_audio, str(background_music), final_audio)
        else:
            import shutil
            shutil.copy2(enhanced_audio, final_audio)

        audio = AudioFileClip(final_audio)
        total_duration = audio.duration
        print(f"  [assembler] Audio: {total_duration:.1f}s (enhanced)", flush=True)

        # Build image clips with professional Ken Burns
        if not images or len(images) == 0:
            clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(5, 5, 15)).with_duration(total_duration)]
        else:
            img_count = len(images)
            img_duration = total_duration / img_count
            clips = []

            for i, img_path in enumerate(images):
                if not os.path.exists(img_path):
                    continue
                try:
                    pil_img = PILImage.open(img_path).convert("RGB")
                    w, h = pil_img.size

                    # Smart crop: center-crop to 16:9
                    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
                    img_ratio = w / h

                    if img_ratio > target_ratio:
                        new_w = int(h * target_ratio)
                        new_h = h
                        x = (w - new_w) // 2
                        y = 0
                    else:
                        new_w = w
                        new_h = int(w / target_ratio)
                        x = 0
                        y = (h - new_h) // 2

                    pil_img = pil_img.crop((x, y, x + new_w, y + new_h))
                    pil_img = pil_img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), PILImage.LANCZOS)

                    # Dark overlay for text readability
                    arr = np.array(pil_img).astype(np.float32)
                    arr *= 0.75
                    arr = arr.astype(np.uint8)

                    base_clip = ImageClip(arr).with_duration(img_duration)

                    # Eased Ken Burns zoom
                    zoom_max = 1.15 if is_short else 1.10
                    zoomed = base_clip.with_effects([
                        Resize(lambda t: 1 + (zoom_max - 1) * ease_in_out(t / max(img_duration, 0.01)))
                    ])

                    clips.append(zoomed)

                except Exception as ex:
                    print(f"  [assembler] Skipping bad image {img_path}: {ex}", flush=True)

            if not clips:
                clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(5, 5, 15)).with_duration(total_duration)]

        print(f"  [assembler] {len(clips)} image clips with eased Ken Burns", flush=True)

        # Professional transitions
        final_clips = []
        for i, clip in enumerate(clips):
            if i > 0:
                fade_dur = min(0.5, clip.duration * 0.15)
                clip = clip.with_effects([CrossFadeIn(fade_dur)])
            else:
                clip = clip.with_effects([FadeIn(0.3)])
            final_clips.append(clip)

        video = concatenate_videoclips(final_clips, method="compose")
        video = video.with_audio(audio)

        # Build overlay layers
        overlay_layers = [video]

        # Animated title at start
        if title:
            title_dur = min(5, total_duration * 0.3)
            title_clip = make_title_animation(title, title_dur)
            if title_clip:
                overlay_layers.append(title_clip)

        # Dynamic captions from script
        if script and len(overlay_layers) < 4:
            import re
            sentences = [s.strip() for s in re.split(r'[.!?]', script) if len(s.strip()) > 20]
            random.shuffle(sentences)
            caption_count = min(2, len(sentences))
            if caption_count > 0:
                spacing = total_duration / (caption_count + 1)
                for idx in range(caption_count):
                    start_t = spacing * (idx + 1)
                    cap_text = sentences[idx][:100]
                    dur = min(4, total_duration - start_t - 0.5)
                    if dur > 1:
                        anims = ["slide_up", "fade_in"]
                        tc = make_animated_text(cap_text, dur, font_size=44, anim_type=random.choice(anims))
                        if tc:
                            tc = tc.with_start(start_t).with_position(("center", "bottom"))
                            overlay_layers.append(tc)

        # Text overlays from param
        if text_overlays:
            for to in text_overlays:
                txt = to.get("text", "")
                start = to.get("start", 0)
                end = to.get("end", total_duration)
                dur = min(end - start, total_duration - start)
                if dur > 1 and txt:
                    tc = make_animated_text(txt, dur, anim_type="fade_in")
                    if tc:
                        overlay_layers.append(tc.with_start(start))

        if len(overlay_layers) > 1:
            video = CompositeVideoClip(overlay_layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        print(f"  [assembler] Rendering video...", flush=True)
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
