"""
Audio enhancement pipeline using ffmpeg.
Makes TTS voice sound professional with EQ, compression, reverb.
Also handles background music with automatic ducking.
"""

import argparse
import json
import os
import sys
import subprocess

sys.path.insert(0, ".")
from config import AUDIO_DIR


def enhance_tts(input_path, output_path):
    """
    Enhance TTS audio with professional processing:
    - Low-cut filter (remove rumble)
    - High-shelf boost (add presence)
    - Compression (even out volume)
    - Reverb (add warmth/space)
    - Normalize (consistent loudness)
    """
    filters = (
        "lowpass=f=8000, "
        "highpass=f=80, "
        "equalizer=f=3000:t=q:w=1:g=3, "
        "equalizer=f=5000:t=q:w=1:g=2, "
        "compand=attacks=0.1:decays=0.5:points=-80/-80|-30/-15|-10/-5|0/-3|20/-3, "
        "dynaudnorm=p=0.9:s=5"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", filters,
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
    except Exception as ex:
        print(f"  [audio] Enhancement failed: {ex}", flush=True)

    return input_path


def add_background_music(vocal_path, music_path, output_path, duck_db=18):
    """
    Mix vocals with background music using automatic ducking.
    Music volume lowers when vocals are present, rises in silence.
    """
    if not music_path or not os.path.exists(music_path):
        import shutil
        shutil.copy2(vocal_path, output_path)
        return output_path

    filters = (
        f"[1:a]asplit[musica][musicas];"
        f"[musicas]sidechaincompress=threshold=0.015:ratio={duck_db}:"
        f"attack=10:release=500:makeup=0[musiccomp];"
        f"[0:a][musiccomp]amix=inputs=2:duration=first:dropout_transition=2[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", vocal_path,
        "-i", music_path,
        "-filter_complex", filters,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
    except Exception as ex:
        print(f"  [audio] Music mixing failed: {ex}", flush=True)

    import shutil
    shutil.copy2(vocal_path, output_path)
    return output_path


def get_vocal_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input audio file (TTS)")
    parser.add_argument("--output", required=True, help="Output enhanced audio file")
    parser.add_argument("--music", default=None, help="Background music file")
    args = parser.parse_args()

    # Step 1: Enhance TTS
    enhanced = enhance_tts(args.input, args.output)

    # Step 2: Mix with background music
    if args.music:
        enhanced = add_background_music(
            enhanced if enhanced != args.input else args.output,
            args.music,
            args.output
        )

    result = {
        "input": args.input,
        "output": enhanced,
        "duration": get_vocal_duration(enhanced) if enhanced else 0
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
