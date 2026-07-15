"""
VARY Voiceover Generator — TTS narration for weekly videos using edge-tts.
Runs locally, no API keys needed. Uses Microsoft's free neural TTS voices.
"""
import asyncio
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, CLIPS_DIR
from modules.utils import find_ffmpeg

_FFMPEG_BIN = find_ffmpeg()

VOICEOVER_DIR = os.path.join(LOG_DIR, "_voiceovers")


def _clean_text(text):
    """Clean text for TTS — remove emojis, special chars that trip edge-tts."""
    import re
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    text = text.replace('"', "'").replace('`', "'")
    return text.strip()


async def _generate_tts_segment(text, output_path, voice="en-US-GuyNeural"):
    """Generate a single TTS audio segment using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="-5Hz")
    await communicate.save(output_path)


def generate_voiceover(story_texts, source_title=""):
    """Generate a full voiceover WAV from story text segments.

    Args:
        story_texts: List of (text, start_ratio) tuples from _generate_story_texts
        source_title: Original movie title for context

    Returns:
        Path to the combined voiceover WAV, or None on failure.
    """
    os.makedirs(VOICEOVER_DIR, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    segments = []
    for text, ratio in story_texts:
        clean = _clean_text(text)
        if not clean:
            continue
        seg_path = os.path.join(VOICEOVER_DIR, f"vo_{run_id}_{len(segments)}.wav")
        segments.append((clean, seg_path))

    if not segments:
        print(f"  [voiceover] No valid text segments to synthesize", flush=True)
        return None

    print(f"  [voiceover] Generating {len(segments)} TTS segments...", flush=True)

    for text, seg_path in segments:
        try:
            asyncio.run(_generate_tts_segment(text, seg_path))
            if not os.path.exists(seg_path) or os.path.getsize(seg_path) < 100:
                print(f"  [voiceover] WARNING: segment too small: {text[:30]}", flush=True)
        except Exception as e:
            print(f"  [voiceover] Failed on segment '{text[:20]}': {e}", flush=True)
            return None

    combined_path = os.path.join(VOICEOVER_DIR, f"voiceover_{run_id}.wav")
    seg_duration = 6.0
    ffmpeg_cmd = [
        "ffmpeg", "-y",
    ]
    filter_parts = []
    input_idx = 0
    total_duration = 0.0
    last_end = 0.0
    gaps = []

    from modules.clip_editor import get_video_duration
    for text, seg_path in segments:
        dur = get_video_duration(seg_path)
        if dur <= 0:
            dur = 6.0
        gaps.append(dur)
        total_duration += dur

    combined_filter = ""
    concat_inputs = []
    for i, (text, seg_path) in enumerate(segments):
        ffmpeg_cmd.extend(["-i", seg_path])
        concat_inputs.append(f"[{i}:a]")

    if len(segments) == 1:
        import shutil
        shutil.copy2(segments[0][1], combined_path)
        print(f"  [voiceover] Single segment: {combined_path}", flush=True)
    else:
        concat_filter = "".join(concat_inputs)
        filter_str = f"{concat_filter}concat=n={len(segments)}:v=0:a=1[vo]"
        ffmpeg_cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[vo]",
            "-ac", "1", "-ar", "44100",
            combined_path,
        ])
        try:
            import subprocess
            subprocess.run(ffmpeg_cmd, capture_output=True, timeout=120)
        except Exception as e:
            print(f"  [voiceover] Concat failed: {e}", flush=True)
            import shutil
            shutil.copy2(segments[0][1], combined_path)

    if os.path.exists(combined_path) and os.path.getsize(combined_path) > 1000:
        print(f"  [voiceover] Generated: {combined_path} ({os.path.getsize(combined_path)} bytes)", flush=True)
        return combined_path

    print(f"  [voiceover] Output invalid", flush=True)
    return None


def cleanup_voiceover(voiceover_path):
    """Delete a voiceover file after use."""
    if voiceover_path and os.path.exists(voiceover_path):
        try:
            os.remove(voiceover_path)
        except Exception:
            pass


if __name__ == "__main__":
    from modules.clip_editor import generate_story_texts
    texts = generate_story_texts("Test Movie: The Dark Knight")
    result = generate_voiceover(texts, "Test Movie")
    if result:
        print(f"Voiceover saved to: {result}")
    else:
        print("Failed")
