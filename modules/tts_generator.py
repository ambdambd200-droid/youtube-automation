"""
Generates voiceover using Edge-TTS (free, high-quality neural TTS).
Call: python -m modules.tts_generator --script "text to speak" --output "output.mp3"
"""

import argparse
import json
import os
import sys
import asyncio

sys.path.insert(0, ".")
from config import TTS_VOICE, AUDIO_DIR, ELEVENLABS_API_KEY, ELEVEN_VOICE_ID

async def generate_tts(text, output_path, voice=None):
    """Generate TTS audio using ElevenLabs (preferred) or Edge-TTS."""

    # Try ElevenLabs first if API key is available
    if ELEVENLABS_API_KEY:
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

            audio = client.text_to_speech.convert(
                voice_id=ELEVEN_VOICE_ID,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128"
            )

            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            return output_path
        except Exception as ex:
            print(f"ElevenLabs error: {ex}. Falling back to Edge-TTS.", file=sys.stderr)

    # Fallback to Edge-TTS
    if voice is None:
        voice = TTS_VOICE

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path
    except Exception as ex:
        print(f"Edge-TTS error: {ex}", file=sys.stderr)
        # Fallback: create a silent audio file
        try:
            import wave
            import struct
            with wave.open(output_path, 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                duration = max(len(text) // 10, 10)
                for _ in range(duration * 22050):
                    wav.writeframes(struct.pack('<h', 0))
            return output_path
        except:
            return None

def split_script_into_segments(script, max_chars=3000):
    """Split long script into segments for TTS processing."""
    paragraphs = [p.strip() for p in script.split('\n') if p.strip()]
    segments = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) < max_chars:
            current += p + "\n"
        else:
            if current:
                segments.append(current.strip())
            current = p + "\n"

    if current:
        segments.append(current.strip())

    return segments if segments else [script]

def get_output_paths(prefix, num_segments):
    """Generate output paths for TTS segments."""
    paths = []
    for i in range(num_segments):
        if num_segments == 1:
            fname = f"{prefix}_voiceover.mp3"
        else:
            fname = f"{prefix}_voiceover_part{i+1:02d}.mp3"
        paths.append(os.path.join(AUDIO_DIR, fname))
    return paths

async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", default="")
    parser.add_argument("--script-file", default=None)
    parser.add_argument("--output-prefix", default="video")
    parser.add_argument("--voice", default=None)
    args = parser.parse_args()

    if args.script_file == "-":
        script = sys.stdin.read()
    elif args.script_file:
        with open(args.script_file, "r", encoding="utf-8") as f:
            script = f.read()
    else:
        script = args.script

    if not script:
        result = {"error": "No script provided", "files": []}
        print(json.dumps(result, ensure_ascii=False))
        return

    if not script:
        result = {"error": "No script provided", "files": []}
        print(json.dumps(result, ensure_ascii=False))
        return

    segments = split_script_into_segments(script)
    output_paths = get_output_paths(args.output_prefix, len(segments))

    os.makedirs(AUDIO_DIR, exist_ok=True)

    generated_files = []
    for i, (seg, path) in enumerate(zip(segments, output_paths)):
        result_path = await generate_tts(seg, path, args.voice)
        if result_path:
            generated_files.append(result_path)
            print(f"Generated: {result_path}", file=sys.stderr)

    result = {
        "segments": len(generated_files),
        "files": generated_files,
        "script_length": len(script)
    }
    print(json.dumps(result, ensure_ascii=False))

# Alias for import by api_server
generate_tts_from_text = generate_tts

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
