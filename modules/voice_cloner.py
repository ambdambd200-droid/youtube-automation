"""
Internal voice cloning engine.
Uses Coqui XTTS (free) to clone user's voice from 18s sample.
Fallback chain: XTTS clone → Edge-TTS enhanced → silence
"""

import argparse
import json
import os
import sys
import asyncio

sys.path.insert(0, ".")
from config import AUDIO_DIR, TTS_VOICE


def clone_voice_segments(segments, speaker_wav, prefix="video", language="en"):
    """Clone voice for multiple script segments. Falls back gracefully."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_files = []
    model = None

    # Attempt to load Coqui XTTS once
    try:
        from TTS.api import TTS
        print(f"  [voice] Loading XTTS-v2 (voice cloning)...", flush=True)
        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        print(f"  [voice] Model loaded successfully", flush=True)
    except Exception as ex:
        print(f"  [voice] XTTS load failed: {ex}", flush=True)
        print(f"  [voice] Falling back to Edge-TTS...", flush=True)

    for i, seg in enumerate(segments):
        if not seg.strip():
            continue

        wav_path = os.path.join(AUDIO_DIR, f"{prefix}_voice_{i+1:02d}.wav")
        mp3_path = os.path.join(AUDIO_DIR, f"{prefix}_voice_{i+1:02d}.mp3")

        # Attempt 1: XTTS cloning
        if model:
            try:
                print(f"  [voice] Cloning segment {i+1}/{len(segments)}...", flush=True)
                model.tts_to_file(text=seg, file_path=wav_path,
                                  speaker_wav=speaker_wav, language=language)
                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
                    audio_files.append(wav_path)
                    continue
            except Exception as ex:
                print(f"  [voice] Clone failed segment {i+1}: {ex}", flush=True)

        # Attempt 2: Edge-TTS fallback
        try:
            import edge_tts
            communicate = edge_tts.Communicate(seg, TTS_VOICE)
            asyncio.run(communicate.save(mp3_path))
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                audio_files.append(mp3_path)
                continue
        except Exception as ex:
            print(f"  [voice] Edge-TTS failed: {ex}", flush=True)

        # Attempt 3: Silence (last resort)
        try:
            import wave, struct
            with wave.open(wav_path, 'w') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                dur = max(len(seg) // 15, 5)
                for _ in range(dur * 22050):
                    w.writeframes(struct.pack('<h', 0))
            audio_files.append(wav_path)
        except:
            pass

    return audio_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script-file", required=True)
    parser.add_argument("--output-prefix", default="video")
    parser.add_argument("--speaker", required=True)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    with open(args.script_file, "r", encoding="utf-8") as f:
        script = f.read()

    segments = [s.strip() for s in script.split('\n') if s.strip()]
    if not segments:
        segments = [script]

    files = clone_voice_segments(segments, args.speaker, args.output_prefix, args.language)
    print(json.dumps({"segments": len(files), "files": files}))


if __name__ == "__main__":
    main()
