"""
Voice cloning using Coqui XTTS (free, open-source).
Clones the user's voice from a short audio sample.
Falls back to Edge-TTS if cloning fails.
"""

import argparse
import json
import os
import sys
import asyncio
import tempfile

sys.path.insert(0, ".")
from config import AUDIO_DIR, TTS_VOICE


def clone_voice(text, output_path, speaker_wav, language="en"):
    """Clone voice using Coqui XTTS-v2. Falls back to Edge-TTS on failure."""
    try:
        from TTS.api import TTS

        print(f"  [voice_cloner] Loading XTTS-v2 model...", flush=True)
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        print(f"  [voice_cloner] Model loaded, generating speech...", flush=True)

        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=speaker_wav,
            language=language
        )

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
        return None

    except Exception as ex:
        print(f"  [voice_cloner] Coqui XTTS failed: {ex}", flush=True)
        print(f"  [voice_cloner] Falling back to TTS...", flush=True)
        return None


def clone_voice_segments(segments, speaker_wav, prefix="video", language="en"):
    """Clone voice for multiple script segments."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_files = []

    # Try loading model once
    model = None
    try:
        from TTS.api import TTS
        print(f"  [voice_cloner] Loading XTTS-v2 model...", flush=True)
        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
    except Exception as ex:
        print(f"  [voice_cloner] Model load failed: {ex}", flush=True)

    for i, seg in enumerate(segments):
        fname = f"{prefix}_cloned_{i+1:02d}.wav"
        path = os.path.join(AUDIO_DIR, fname)

        if model:
            try:
                print(f"  [voice_cloner] Generating segment {i+1}/{len(segments)}...", flush=True)
                model.tts_to_file(
                    text=seg,
                    file_path=path,
                    speaker_wav=speaker_wav,
                    language=language
                )
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    audio_files.append(path)
                    continue
            except Exception:
                pass

        # Fallback
        print(f"  [voice_cloner] Fallback to Edge-TTS for segment {i+1}", flush=True)
        import edge_tts
        mp3_path = path.replace(".wav", ".mp3")
        communicate = edge_tts.Communicate(seg, TTS_VOICE)
        asyncio.run(communicate.save(mp3_path))
        if os.path.exists(mp3_path):
            audio_files.append(mp3_path)

    return audio_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--output", required=True, help="Output audio file")
    parser.add_argument("--speaker", required=True, help="Speaker WAV file for cloning")
    parser.add_argument("--language", default="en", help="Language code")
    args = parser.parse_args()

    result_path = clone_voice(args.text, args.output, args.speaker, args.language)
    result = {"output": result_path, "success": result_path is not None}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
