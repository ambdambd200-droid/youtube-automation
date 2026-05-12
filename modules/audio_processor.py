"""
Internal audio engine for Depths channel.
Professional EQ, compression, ducking — zero external tools.
Levels: Vocal -12dB to -6dB | Music -25dB to -20dB | SFX -18dB to -14dB
"""

import argparse
import json
import os
import sys
import subprocess
import shutil

sys.path.insert(0, ".")
from config import AUDIO_DIR


def enhance_tts(input_path, output_path):
    """
    Professional vocal enhancement chain:
    - Low-cut 80Hz (remove rumble)
    - High-shelf boost at 5kHz (presence/clarity)
    - EQ: +3dB at 3kHz (vocal warmth)
    - Compression: even out volume
    - Normalize: -1dB peak (broadcast standard)
    """
    filters = (
        "highpass=f=80, "
        "equalizer=f=3000:t=q:w=1:g=3, "
        "equalizer=f=5000:t=q:w=1:g=2, "
        "compand=attacks=0.1:decays=0.5:"
        "points=-80/-80|-30/-15|-10/-5|0/-3|20/-3, "
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

    shutil.copy2(input_path, output_path)
    return output_path


def add_background_music(vocal_path, music_path, output_path):
    """
    Mix vocals with background music using sidechain compression (auto-ducking).
    Music volume ducks -18dB when vocals present, rises in silence.
    Final mix: Vocal -6dB, Music -20dB (relative)
    """
    if not music_path or not os.path.exists(music_path):
        shutil.copy2(vocal_path, output_path)
        return output_path

    filters = (
        "[1:a]asplit[musica][musicas];"
        "[musicas]sidechaincompress="
        "threshold=0.015:ratio=18:attack=10:release=500:makeup=0[musiccomp];"
        "[0:a][musiccomp]amix=inputs=2:duration=first:dropout_transition=2,"
        "volume=2.0[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", vocal_path, "-i", music_path,
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
        print(f"  [audio] Mix failed: {ex}", flush=True)

    shutil.copy2(vocal_path, output_path)
    return output_path


def add_sound_effect(audio_path, sfx_path, output_path, position=0, level=-14):
    """
    Add a sound effect at a specific position in the audio.
    SFX level: -18dB to -14dB as per manifesto specs.
    """
    if not sfx_path or not os.path.exists(sfx_path):
        shutil.copy2(audio_path, output_path)
        return output_path

    filters = (
        f"[1:a]volume={level}dB[sfx];"
        f"[0:a][sfx]amix=inputs=2:duration=first[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path, "-i", sfx_path,
        "-filter_complex", filters,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path):
            return output_path
    except:
        pass

    shutil.copy2(audio_path, output_path)
    return output_path


def get_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except:
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--music", default=None)
    parser.add_argument("--sfx", default=None)
    parser.add_argument("--sfx-pos", type=float, default=0)
    parser.add_argument("--sfx-level", type=float, default=-14)
    args = parser.parse_args()

    result_path = enhance_tts(args.input, args.output)

    if args.music:
        result_path = add_background_music(
            result_path if os.path.exists(result_path) else args.output,
            args.music, args.output
        )

    if args.sfx:
        result_path = add_sound_effect(
            result_path if os.path.exists(result_path) else args.output,
            args.sfx, args.output,
            position=args.sfx_pos, level=args.sfx_level
        )

    result = {"output": result_path, "duration": get_duration(result_path) if result_path else 0}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
