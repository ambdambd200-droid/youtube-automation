"""
Internal video engine for Depths channel.
Implements professional pacing phases, freeze+zoom, dynamic text.
Zero external dependencies — pure MoviePy + internal effects.
"""

import argparse
import json
import os
import sys
import math
import random

sys.path.insert(0, ".")
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS


def ease_in_out(t):
    """Smooth ease-in-out curve. Clamped to [0, 1]."""
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def phase_cuts(phase, total_duration):
    """Calculate cut interval based on video phase.
    Hook (0-15s): fast cuts every 1-2s
    Build (15s-40%): cuts every 3-5s
    Peak (40-65%): cuts every 2-3s
    Ending (65-100%): cuts every 4-6s
    """
    hook_end = min(15, total_duration * 0.15)
    build_end = total_duration * 0.40
    peak_end = total_duration * 0.65

    if phase == "hook":
        return random.uniform(1.0, 2.0)
    elif phase == "build":
        return random.uniform(3.0, 5.0)
    elif phase == "peak":
        return random.uniform(2.0, 3.0)
    else:
        return random.uniform(4.0, 6.0)


def get_phase(t, total_duration):
    """Determine which phase a timestamp falls in."""
    hook_end = min(15, total_duration * 0.15)
    build_end = total_duration * 0.40
    peak_end = total_duration * 0.65

    if t < hook_end:
        return "hook"
    elif t < build_end:
        return "build"
    elif t < peak_end:
        return "peak"
    else:
        return "ending"


def find_key_moments(script, total_duration):
    """Extract key moments from script for text overlays."""
    import re
    moments = []

    if not script:
        return moments

    # Find "wait" moments
    for m in re.finditer(r'(?i)\b(wait|but here\'s|this is where|and then)\b', script):
        rel_pos = m.start() / max(len(script), 1)
        t = rel_pos * total_duration
        moments.append({"time": t, "type": "wait", "text": "wait..."})

    # Find question marks
    for m in re.finditer(r'([^.]*\?)', script):
        rel_pos = m.start() / max(len(script), 1)
        t = rel_pos * total_duration
        q = m.group(1).strip()[:60]
        if len(q) > 10:
            moments.append({"time": t, "type": "question", "text": q})

    # Find numbers with impact
    for m in re.finditer(r'\b(\d{2,}%|\d{3,})\b', script):
        rel_pos = m.start() / max(len(script), 1)
        t = rel_pos * total_duration
        moments.append({"time": t, "type": "number", "text": m.group(1)})

    return moments[:5]


def make_text_layer(text, duration, anim_type="slide_up", font_size=52,
                    text_color=(255, 255, 255), bar_color=(0, 0, 0), is_word_by_word=False):
    """Create animated text overlay with professional motion."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import VideoClip

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", None
        ]:
            try:
                font = ImageFont.truetype(fp, font_size) if fp else ImageFont.load_default()
                break
            except:
                continue

        # Word wrap
        draw_test = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = text.split()
        lines, current = [], ""
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

        line_h = font_size + 15
        bar_h = len(lines) * line_h + 40

        def make_frame(t):
            progress = min(t / max(duration, 0.01), 1)

            offset, alpha = 0, 1
            if anim_type == "slide_up":
                offset = int(60 * (1 - ease_in_out(min(progress * 2, 1))))
                alpha = min(progress * 4, 1)
            elif anim_type == "fade_in":
                alpha = min(progress * 3, 1)
            elif anim_type == "scale_in":
                alpha = min(progress * 3, 1)

            bar = Image.new("RGBA", (VIDEO_WIDTH, bar_h),
                           (*bar_color, int(160 * alpha)))
            draw = ImageDraw.Draw(bar)

            y_pos = 20 + offset

            if is_word_by_word:
                # Dynamic word highlighting - simplified for now
                words = text.split()
                num_words = len(words)
                # current_word_idx = int(progress * num_words)

            for li, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
                x = (VIDEO_WIDTH - w) // 2
                y = y_pos + li * line_h

                # Loristy shadow/glow
                for ox, oy in [(4, 4), (2, 2)]:
                    draw.text((x + ox, y + oy), line, fill=(0, 0, 0, int(220 * alpha)), font=font)

                draw.text((x, y), line, fill=(*text_color, int(255 * alpha)), font=font)

            return np.array(bar)

        return VideoClip(make_frame, duration=duration).with_position(("center", "bottom"))

    except Exception as ex:
        print(f"  [video] Text error: {ex}", flush=True)
        return None


def make_big_word(text, duration):
    """Create a single big word overlay for shock moments."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import VideoClip

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None
        ]:
            try:
                font = ImageFont.truetype(fp, 90) if fp else ImageFont.load_default()
                break
            except:
                continue

        def make_frame(t):
            progress = min(t / max(duration, 0.01), 1)
            alpha = min(progress * 5, 1)
            p = ease_in_out(min(progress * 3, 1))

            canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (VIDEO_WIDTH - tw) // 2
            y = (VIDEO_HEIGHT - th) // 2

            for ox, oy in [(4, 4), (3, 3)]:
                draw.text((x + ox, y + oy), text, fill=(0, 0, 0, int(200 * alpha)), font=font)
            draw.text((x, y), text, fill=(200, 40, 40, int(255 * alpha)), font=font)

            return np.array(canvas)

        return VideoClip(make_frame, duration=duration)

    except Exception as ex:
        print(f"  [video] Big word error: {ex}", flush=True)
        return None


def make_title_animation(text, duration):
    """Animated title that scales and fades in at center."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy import VideoClip

        font = None
        for fp in [
            "C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None
        ]:
            try:
                font = ImageFont.truetype(fp, 58) if fp else ImageFont.load_default()
                break
            except:
                continue

        draw_test = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words = text.split()
        lines, current = [], ""
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
            fw, fh = int(VIDEO_WIDTH * scale), int((len(lines) * line_h + 40) * scale)

            canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
            overlay = Image.new("RGBA", (fw, fh), (0, 0, 0, int(180 * alpha)))
            draw = ImageDraw.Draw(overlay)

            for li, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                w, y = bbox[2] - bbox[0], 20 + li * line_h
                x = (fw - w) // 2
                for ox, oy in [(3, 3), (2, 2)]:
                    draw.text((x + ox, y + oy), line, fill=(0, 0, 0, int(200 * alpha)), font=font)
                draw.text((x, y), line, fill=(255, 215, 0, int(255 * alpha)), font=font)

            canvas.paste(overlay, ((VIDEO_WIDTH - fw) // 2, (VIDEO_HEIGHT - fh) // 2))
            return np.array(canvas)

        return VideoClip(make_frame, duration=duration)

    except Exception as ex:
        print(f"  [video] Title error: {ex}", flush=True)
        return None


def assemble_video(images, audio_path, output_path, background_music=None,
                   text_overlays=None, is_short=True, title=None, script=None, cinematic=True):
    """Assemble professional video with phase-based pacing, effects, and text animations."""
    try:
        from moviepy import (
            AudioFileClip, ImageClip, VideoClip,
            CompositeVideoClip, concatenate_videoclips, ColorClip
        )
        from PIL import Image as PILImage
        import numpy as np
        from moviepy.video.fx import Resize, CrossFadeIn, FadeIn, FadeOut
        from moviepy.audio.fx import AudioLoop, MultiplyVolume
        from moviepy import CompositeAudioClip
        from modules.audio_processor import enhance_tts, add_background_music

        # ── Audio pipeline ─────────────────────────────────
        print(f"  [video] Processing audio...", flush=True)
        enhanced = os.path.join(os.path.dirname(output_path), "enhanced_audio.mp3")
        enhance_tts(audio_path, enhanced)

        final_audio_p = os.path.join(os.path.dirname(output_path), "final_audio.mp3")
        if background_music and os.path.exists(str(background_music)):
            add_background_music(enhanced, str(background_music), final_audio_p)
        else:
            import shutil
            shutil.copy2(enhanced, final_audio_p)

        audio = AudioFileClip(final_audio_p)
        total_duration = audio.duration
        print(f"  [video] Audio: {total_duration:.1f}s", flush=True)

        # ── Media clips (Images and Videos) ────────────────
        from moviepy import VideoFileClip
        if not images:
            clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(5, 5, 15)).with_duration(total_duration)]
        else:
            # Phase-based media distribution
            images_available = [p for p in images if os.path.exists(p)]
            if not images_available:
                clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(5, 5, 15)).with_duration(total_duration)]
            else:
                clips = []
                t = 0.0
                media_idx = 0

                while t < total_duration - 0.5:
                    phase = get_phase(t, total_duration)
                    cut_dur = min(phase_cuts(phase, total_duration), total_duration - t)

                    media_path = images_available[media_idx % len(images_available)]
                    media_idx += 1

                    is_video_file = any(media_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi'])

                    try:
                        if is_video_file:
                            # Process Video Clip
                            v_clip = VideoFileClip(media_path).with_effects([Resize((VIDEO_WIDTH, VIDEO_HEIGHT))]).without_audio()
                            if v_clip.duration > cut_dur:
                                start_t = random.uniform(0, v_clip.duration - cut_dur)
                                v_clip = v_clip.with_section(start_t, start_t + cut_dur)
                            else:
                                v_clip = v_clip.with_duration(cut_dur)

                            # Apply subtle darkening for text readability
                            # Using a color effect would be better, but for now we'll just use the clip
                            clips.append(v_clip)
                        else:
                            # Process Image Clip
                            pil_img = PILImage.open(media_path).convert("RGB")
                            w, h = pil_img.size
                            ratio = VIDEO_WIDTH / VIDEO_HEIGHT
                            img_r = w / h

                            if img_r > ratio:
                                nw, nh = int(h * ratio), h
                                cx, cy = (w - nw) // 2, 0
                            else:
                                nw, nh = w, int(w / ratio)
                                cx, cy = 0, (h - nh) // 2

                            pil_img = pil_img.crop((cx, cy, cx + nw, cy + nh))
                            pil_img = pil_img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), PILImage.LANCZOS)

                            arr = np.array(pil_img).astype(np.float32)
                            arr *= 0.75
                            arr = arr.astype(np.uint8)

                            base = ImageClip(arr).with_duration(cut_dur)

                            zoom_max = {"hook": 1.20, "build": 1.10, "peak": 1.25, "ending": 1.08}[phase]
                            zoom_dir = random.choice([1, -1])

                            # Safety: ensures cut_dur is never zero
                            safe_dur = max(cut_dur, 0.1)

                            if zoom_dir == 1:
                                zoomed = base.with_effects([
                                    Resize(lambda t: max(0.01, 1 + (zoom_max - 1) * ease_in_out(t / safe_dur)))
                                ]).with_duration(cut_dur)
                            else:
                                zoomed = base.with_effects([
                                    Resize(lambda t: max(0.01, zoom_max - (zoom_max - 1) * ease_in_out(t / safe_dur)))
                                ]).with_duration(cut_dur)

                            clips.append(zoomed)
                    except Exception as e:
                        print(f"Error processing media {media_path}: {e}")
                        clips.append(ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(5, 5, 15)).with_duration(cut_dur))

                    t += cut_dur

        print(f"  [video] {len(clips)} clips with phase-based pacing", flush=True)

        # ── Transitions ──────────────────────────────────────
        final_clips = []
        for i, clip in enumerate(clips):
            if i > 0:
                fd = min(0.4, clip.duration * 0.15)
                clip = clip.with_effects([CrossFadeIn(fd)])
            else:
                clip = clip.with_effects([FadeIn(0.3)])
            final_clips.append(clip)

        video = concatenate_videoclips(final_clips, method="compose")
        video = video.with_audio(audio)
        layers = [video]

        # Cinematic: Add SFX layers
        sfx_layers = []
        sfx_dir = "assets/sfx"
        if os.path.exists(sfx_dir):
            sfx_files = [os.path.join(sfx_dir, f) for f in os.listdir(sfx_dir) if f.endswith(('.mp3', '.wav'))]
            if sfx_files:
                # Add a 'swoosh' at every transition
                t_accum = 0
                for clip in final_clips[:-1]:
                    t_accum += clip.duration
                    swoosh = random.choice(sfx_files)
                    try:
                        sfx_clip = AudioFileClip(swoosh).with_start(t_accum - 0.2).with_effects([MultiplyVolume(0.3)])
                        sfx_layers.append(sfx_clip)
                    except:
                        pass

        if sfx_layers:
            final_audio_combined = CompositeAudioClip([audio] + sfx_layers)
            video = video.with_audio(final_audio_combined)
            layers[0] = video

        # ── Animated title ──────────────────────────────────
        if title:
            td = min(5, total_duration * 0.25)
            tc = make_title_animation(title, td)
            if tc:
                layers.append(tc)

        # ── Key moments from script ──────────────────────────
        if script:
            moments = find_key_moments(script, total_duration)
            for m in moments:
                mt = m["time"]
                if mt > total_duration - 2:
                    continue
                md = min(3, total_duration - mt - 0.5)
                if md < 0.5:
                    continue

                if m["type"] == "number":
                    # Big number overlay
                    clip = make_big_word(m["text"], md).with_start(mt)
                    if clip:
                        layers.append(clip)
                elif m["type"] == "wait":
                    clip = make_text_layer(m["text"], md, font_size=58,
                                           text_color=(200, 40, 40), anim_type="scale_in")
                    if clip:
                        layers.append(clip.with_start(mt))
                elif m["type"] == "question":
                    clip = make_text_layer(m["text"], md, font_size=44,
                                           anim_type="fade_in")
                    if clip:
                        layers.append(clip.with_start(mt))

            # Add 1-2 random captions if not enough moments
            if len(moments) < 2:
                import re as re_mod
                sentences = [s.strip() for s in re_mod.split(r'[.!?]', script) if len(s.strip()) > 25]
                random.shuffle(sentences)
                for i, sent in enumerate(sentences[:2]):
                    st = total_duration * (0.3 + i * 0.25)
                    sd = min(4, total_duration - st - 0.5)
                    if sd > 1:
                        clip = make_text_layer(sent[:100], sd, font_size=42,
                                               anim_type=random.choice(["slide_up", "fade_in"]))
                        if clip:
                            layers.append(clip.with_start(st))

        # ── External text overlays ──────────────────────────
        if text_overlays:
            for to in text_overlays:
                txt = to.get("text", "")
                st = to.get("start", 0)
                sd = min(to.get("end", total_duration) - st, total_duration - st)
                if sd > 1 and txt:
                    clip = make_text_layer(txt, sd, anim_type="fade_in")
                    if clip:
                        layers.append(clip.with_start(st))

        if len(layers) > 1:
            video = CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        # ── Render ──────────────────────────────────────────
        print(f"  [video] Rendering (phase-based pacing)...", flush=True)
        video.write_videofile(
            output_path, codec="libx264", audio_codec="aac",
            fps=FPS, preset="veryfast", bitrate="3000k",
            ffmpeg_params=["-movflags", "+faststart"], logger=None
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

    data = {}
    if args.json:
        data = json.loads(args.json)

    video_path = assemble_video(
        images=data.get("images", args.images or []),
        audio_path=data.get("audio", args.audio),
        output_path=data.get("output", args.output),
        background_music=data.get("background", args.background),
        is_short=(data.get("type", args.type) == "short"),
        title=data.get("title", args.title),
        script=data.get("script", args.script)
    )

    print(json.dumps({"output": video_path}))


if __name__ == "__main__":
    main()
