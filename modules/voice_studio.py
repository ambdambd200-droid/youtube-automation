"""
Voice Studio — unified TTS interface with voice cloning support.

Engines (in priority order):
1. gTTS — Natural for short phrases (hooks)
2. edge-tts — Fallback with voice pool
3. Fish Audio API — Voice cloning + TTS (needs API key + credits)
4. Piper TTS — Local, free, fast (CPU), multi-lingual
5. SpeechT5 — Local ML TTS (if models downloaded)

Audio post-processing:
- Loudnorm (-14 LUFS)
- High-pass filter (80Hz rumble removal)
- Presence boost (+3dB at 3-5kHz)
- Light compression
"""
import os
import random
import subprocess
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_FFMPEG = None
_FFPROBE = None
_CLONED_VOICE_ID = None
_PIPER_VOICE = None  # Piper voice model (e.g., 'en_US-lessac-medium')


def _get_ffmpeg():
    global _FFMPEG
    if _FFMPEG is None:
        from modules.utils import find_ffmpeg
        _FFMPEG = find_ffmpeg()
    return _FFMPEG


def _get_ffprobe():
    global _FFPROBE
    if _FFPROBE is None:
        from modules.utils import find_ffprobe
        _FFPROBE = find_ffprobe()
    return _FFPROBE


def _run_cmd(cmd, timeout=60):
    """Run a command, return (success, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, "", str(e)


def _process_audio(input_path, output_path):
    """Apply post-processing to make TTS audio sound more natural."""
    cmd = [
        _get_ffmpeg(), "-y", "-i", input_path,
        "-af", (
            "highpass=f=80,"           # Remove rumble
            "equalizer=f=3000:width_type=h:width=2000:g=3,"  # Presence boost
            "acompressor=threshold=-20dB:ratio=3:attack=5:release=50,"  # Light compression
            "loudnorm=I=-16:LRA=7:TP=-1"  # Normalize loudness
        ),
        "-ar", "48000", "-ac", "1",
        output_path,
    ]
    success, _, _ = _run_cmd(cmd, timeout=30)
    if not success:
        # If processing fails, just copy the file
        import shutil
        shutil.copy2(input_path, output_path)
    return output_path


# ── Engine 1: gTTS (Google Text-to-Speech) — Most natural for short phrases ──

def _generate_gtts(text, output_path):
    """Generate TTS using Google Text-to-Speech."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 200
    except Exception as e:
        print(f"  [voice] gTTS failed: {e}", flush=True)
        return False


# ── Engine 2: edge-tts (Microsoft Edge voices) — With voice pool ──

def _generate_edge_tts(text, output_path, voice=None, rate="+0%", pitch="+0Hz"):
    """Generate TTS using edge-tts with specified or random voice."""
    try:
        import edge_tts
        import asyncio
        if voice is None:
            voice = random.choice([
                "en-US-GuyNeural",
                "en-US-DavisNeural",
                "en-GB-RyanNeural",
                "en-GB-SoniaNeural",
                "en-AU-WilliamNeural",
            ])
        asyncio.run(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(output_path))
        return os.path.exists(output_path) and os.path.getsize(output_path) > 200
    except Exception as e:
        print(f"  [voice] edge-tts failed: {e}", flush=True)
        return False


# ── Engine 3: Fish Audio API — Voice cloning + TTS (needs API key + credits) ──

def _generate_fish_audio(text, output_path, reference_audio=None, api_key=None, voice_id=None):
    """
    Generate TTS using Fish Audio API with optional voice cloning.
    Requires FISH_API_KEY environment variable or api_key parameter.
    If voice_id provided, uses that cloned voice.
    If reference_audio provided, creates a new cloned voice.
    """
    try:
        import requests
        api_key = api_key or os.getenv("FISH_API_KEY")
        if not api_key:
            return False

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model": "s2-pro",
            "format": "wav",
        }

        if voice_id:
            payload["voice_id"] = voice_id

        response = requests.post(
            "https://api.fish.audio/v1/tts",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return os.path.getsize(output_path) > 200

        if response.status_code == 402:
            print(f"  [voice] Fish Audio: Insufficient credits - add funds at https://fish.audio/app/developers", flush=True)
        elif response.status_code != 200:
            print(f"  [voice] Fish Audio TTS failed: {response.status_code} - {response.text[:200]}", flush=True)
        return False
    except Exception as e:
        print(f"  [voice] Fish Audio API failed: {e}", flush=True)
        return False


def _generate_fish_audio_with_cloned(text, output_path, voice_id):
    """Generate TTS using a pre-cloned voice."""
    return _generate_fish_audio(text, output_path, voice_id=voice_id, api_key=os.getenv("FISH_API_KEY"))


def clone_voice_fish(reference_audio_path, voice_name="user_voice"):
    """
    Clone voice from reference audio using Fish Audio API.
    Returns voice ID or None.
    """
    api_key = os.getenv("FISH_API_KEY")
    if not api_key:
        print(f"  [voice] Voice cloning needs FISH_API_KEY env var", flush=True)
        return None

    try:
        import requests
        headers = {"Authorization": f"Bearer {api_key}"}

        # Convert to WAV if needed (Fish Audio prefers WAV)
        wav_path = reference_audio_path
        if reference_audio_path.lower().endswith(('.ogg', '.opus', '.mp3', '.m4a')):
            wav_path = reference_audio_path.rsplit('.', 1)[0] + '_converted.wav'
            cmd = [
                _get_ffmpeg(), "-y", "-i", reference_audio_path,
                "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le",
                wav_path,
            ]
            success, _, err = _run_cmd(cmd, timeout=30)
            if not success:
                print(f"  [voice] Audio conversion failed: {err}", flush=True)
                wav_path = reference_audio_path

        with open(wav_path, "rb") as f:
            audio_data = f.read()

        print(f"  [voice] Uploading reference audio ({len(audio_data)} bytes)...", flush=True)
        
        # Use visibility=private to avoid cover_image requirement for public models
        files = {
            "voices": (os.path.basename(wav_path), audio_data, "audio/wav"),
        }
        data = {
            "title": voice_name,
            "type": "tts",
            "train_mode": "fast",
            "visibility": "private",
        }
        response = requests.post(
            "https://api.fish.audio/model",
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

        if wav_path != reference_audio_path and os.path.exists(wav_path):
            os.remove(wav_path)

        if response.status_code in (200, 201):
            voice_data = response.json()
            voice_id = voice_data.get("id") or voice_data.get("_id")
            print(f"  [voice] Voice cloned successfully: {voice_id}", flush=True)
            return voice_id

        print(f"  [voice] Cloning failed: {response.status_code} - {response.text[:300]}", flush=True)
        return None
    except Exception as e:
        print(f"  [voice] Cloning error: {e}", flush=True)
        return None


# ── Engine 4: Piper TTS — Local, free, fast (CPU), multi-lingual ──

def _generate_piper_tts(text, output_path, voice_model=None, speaker=None):
    """
    Generate TTS using Piper (local, free, fast on CPU).
    Requires piper-tts package and voice model (.onnx file).
    
    Args:
        text: Text to synthesize
        output_path: Output WAV file path
        voice_model: Piper voice model path (e.g., 'piper_models/en_US-lessac-medium.onnx')
        speaker: Speaker ID for multi-speaker models
    
    Returns True on success.
    """
    global _PIPER_VOICE
    
    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
    except ImportError:
        print(f"  [voice] Piper not installed (pip install piper-tts)", flush=True)
        return False
    
    # Default to a good English voice
    if voice_model is None:
        voice_model = "piper_models/en_US-lessac-medium.onnx"
    
    try:
        # Load voice (cached)
        if _PIPER_VOICE is None or _PIPER_VOICE.config.name != voice_model:
            print(f"  [voice] Loading Piper voice: {voice_model}", flush=True)
            _PIPER_VOICE = PiperVoice.load(voice_model)
        
        # Generate audio with SynthesisConfig for speaker
        syn_config = SynthesisConfig(speaker_id=speaker or 0)
        with open(output_path, "wb") as f:
            for chunk in _PIPER_VOICE.synthesize(text, syn_config=syn_config):
                f.write(chunk.audio_int16_bytes)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 200:
            print(f"  [voice] Piper TTS generated: {voice_model}", flush=True)
            return True
        
        return False
    except Exception as e:
        print(f"  [voice] Piper TTS failed: {e}", flush=True)
        return False

def set_piper_voice(voice_model):
    """Set the Piper voice model to use."""
    global _PIPER_VOICE
    _PIPER_VOICE = None  # Force reload
    print(f"  [voice] Piper voice set to: {voice_model}", flush=True)


def set_cloned_voice(voice_id):
    """Set the global cloned voice ID for TTS generation."""
    global _CLONED_VOICE_ID
    _CLONED_VOICE_ID = voice_id
    print(f"  [voice] Cloned voice set: {voice_id}", flush=True)


def get_cloned_voice():
    """Get the current cloned voice ID."""
    return _CLONED_VOICE_ID


def generate_hook_voice(text, output_path, process=True):
    """
    Generate a hook voiceover (short phrase like 'wait for it.').
    Priority: Fish Audio (cloned) → gTTS → edge-tts → Piper (local free)
    """
    raw_path = output_path + ".raw.mp3"

    # If cloned voice is available, try Fish Audio first for consistency
    cloned_id = get_cloned_voice()
    if cloned_id:
        if _generate_fish_audio_with_cloned(text, raw_path, cloned_id):
            print(f"  [voice] Hook: Fish Audio (cloned)", flush=True)
            if process:
                return _process_audio(raw_path, output_path)
            else:
                import shutil
                shutil.copy2(raw_path, output_path)
                return True

    # Try gTTS first for natural sound
    if _generate_gtts(text, raw_path):
        print(f"  [voice] Hook: gTTS (natural)", flush=True)
        if process:
            return _process_audio(raw_path, output_path)
        else:
            import shutil
            shutil.copy2(raw_path, output_path)
            return True

    # Fallback to edge-tts
    if _generate_edge_tts(text, raw_path, rate="+5%", pitch="+0Hz"):
        print(f"  [voice] Hook: edge-tts (fallback)", flush=True)
        if process:
            return _process_audio(raw_path, output_path)
        else:
            import shutil
            shutil.copy2(raw_path, output_path)
            return True

    # Free local fallback: Piper TTS
    if _generate_piper_tts(text, raw_path):
        print(f"  [voice] Hook: Piper TTS (local free)", flush=True)
        if process:
            return _process_audio(raw_path, output_path)
        else:
            import shutil
            shutil.copy2(raw_path, output_path)
            return True

    return False


def generate_analysis_voice(text, output_path, process=True):
    """
    Generate analysis narration (longer text).
    Priority: Fish Audio (cloned) → edge-tts → gTTS → Piper (local free)
    """
    raw_path = output_path + ".raw.mp3"

    # If cloned voice is available, try Fish Audio first
    cloned_id = get_cloned_voice()
    if cloned_id:
        if _generate_fish_audio_with_cloned(text, raw_path, cloned_id):
            print(f"  [voice] Analysis: Fish Audio (cloned)", flush=True)
            if process:
                return _process_audio(raw_path, output_path)
            else:
                import shutil
                shutil.copy2(raw_path, output_path)
                return True

    # Try different edge-tts voices
    voices = [
        "en-US-GuyNeural",
        "en-US-DavisNeural",
        "en-GB-RyanNeural",
        "en-GB-SoniaNeural",
    ]

    for voice in voices:
        if _generate_edge_tts(text, raw_path, voice=voice, rate="+5%", pitch="+0Hz"):
            print(f"  [voice] Analysis: {voice}", flush=True)
            if process:
                return _process_audio(raw_path, output_path)
            else:
                import shutil
                shutil.copy2(raw_path, output_path)
                return True

    # Fallback: gTTS
    if _generate_gtts(text, raw_path):
        print(f"  [voice] Analysis: gTTS (fallback)", flush=True)
        if process:
            return _process_audio(raw_path, output_path)
        else:
            import shutil
            shutil.copy2(raw_path, output_path)
            return True

    # Free local fallback: Piper TTS
    if _generate_piper_tts(text, raw_path):
        print(f"  [voice] Analysis: Piper TTS (local free)", flush=True)
        if process:
            return _process_audio(raw_path, output_path)
        else:
            import shutil
            shutil.copy2(raw_path, output_path)
            return True

    return False


def clone_voice(reference_audio_path, voice_name="user_voice"):
    """
    Clone voice from reference audio. Returns voice ID or None.
    Currently supports Fish Audio API (needs FISH_API_KEY).
    Placeholder for future local Fish Speech integration.
    """
    api_key = os.getenv("FISH_API_KEY")
    if not api_key:
        print(f"  [voice] Voice cloning needs FISH_API_KEY env var", flush=True)
        return None

    try:
        import requests
        headers = {"Authorization": f"Bearer {api_key}"}

        with open(reference_audio_path, "rb") as f:
            audio_data = f.read()

        response = requests.post(
            "https://api.fish.audio/model",
            headers=headers,
            files={"voices": (os.path.basename(reference_audio_path), audio_data, "audio/wav")},
            data={"title": voice_name, "type": "tts"},
            timeout=30,
        )

        if response.status_code == 200:
            voice_data = response.json()
            voice_id = voice_data.get("id")
            print(f"  [voice] Voice cloned: {voice_id}", flush=True)
            return voice_id

        print(f"  [voice] Cloning failed: {response.status_code}", flush=True)
        return None
    except Exception as e:
        print(f"  [voice] Cloning error: {e}", flush=True)
        return None


if __name__ == "__main__":
    # Quick test
    out = r"C:\Users\A\AppData\Local\Temp\voice_studio_test.wav"
    if generate_hook_voice("The eye is the tell. Watch closely.", out):
        print(f"Success: {os.path.getsize(out)} bytes")
    else:
        print("All engines failed")
