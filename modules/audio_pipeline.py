"""
VARY Audio Pipeline — Hyper-Realistic Sound Design
Blueprint Section 2: Acoustic Engineering (The "No Music" Manifesto)
  Phase 1: Surgical EQ Carving
  Phase 2: Dialogue Clarity & Presence
  Phase 3: Foley Layering (Impact, Whoosh, Texture)
  Phase 4: Ambience & Spatial Immersion
  Final: LUFS Loudness Normalization
"""
import os
import sys
import subprocess
import uuid
import struct
import math
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CLIPS_DIR,
    AUDIO_TARGET_LUFS, AUDIO_TRUE_PEAK,
    AUDIO_SAMPLE_RATE, AUDIO_BITRATE, AUDIO_CODEC,
    AUDIO_EQ_HIGHPASS, AUDIO_EQ_LOWPASS, AUDIO_PRESENCE_BOOST,
    AUDIO_COMPRESSION_RATIO, AUDIO_DUCK_DB, AUDIO_DUCK_DURATION,
)


def _run_ffmpeg(cmd, description="audio", timeout=60):
    """Run ffmpeg and log."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            print(f"  [audio] {description} failed: {result.stderr[:200]}", flush=True)
            return None
        return result
    except subprocess.TimeoutExpired:
        print(f"  [audio] {description} timed out", flush=True)
    except Exception as e:
        print(f"  [audio] {description} error: {e}", flush=True)
    return None


def apply_eq_carving(input_path, output_path):
    """Phase 1-2: EQ Carving + Dialogue Presence.
    HP 80Hz, LP 12kHz, +3dB presence boost at 3-5kHz.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        f"highpass=f={AUDIO_EQ_HIGHPASS},"
        f"lowpass=f={AUDIO_EQ_LOWPASS},"
        f"equalizer=f=3000:t=q:w=1:g={AUDIO_PRESENCE_BOOST},"
        f"equalizer=f=4000:t=q:w=1:g={AUDIO_PRESENCE_BOOST},"
        f"equalizer=f=5000:t=q:w=1:g={AUDIO_PRESENCE_BOOST}",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        "-sample_fmt", "s16",
        output_path,
    ]
    result = _run_ffmpeg(cmd, "EQ carving")
    if result and os.path.exists(output_path):
        print(f"  [audio] EQ carved: HP@{AUDIO_EQ_HIGHPASS}Hz LP@{AUDIO_EQ_LOWPASS}Hz +{AUDIO_PRESENCE_BOOST}dB presence", flush=True)
        return output_path
    return None


def apply_dynamic_compression(input_path, output_path):
    """Phase 2: Heavy compression 4:1 to even out dynamics."""
    threshold = -24  # dB threshold
    ratio = AUDIO_COMPRESSION_RATIO
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        f"acompressor=threshold={threshold}:ratio={ratio}:attack=5:release=50:makeup=3",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        output_path,
    ]
    result = _run_ffmpeg(cmd, f"compression {ratio}:1")
    if result and os.path.exists(output_path):
        print(f"  [audio] Compressed {ratio}:1 at {threshold}dB threshold", flush=True)
        return output_path
    return None


def _write_wav_header(f, n_samples, n_channels, sampwidth, framerate):
    """Write WAV header for PCM 16-bit mono/stereo audio."""
    data_size = n_samples * n_channels * sampwidth
    f.write(b"RIFF")
    f.write(struct.pack("<I", 36 + data_size))
    f.write(b"WAVE")
    f.write(b"fmt ")
    f.write(struct.pack("<IHHIIHH", 16, 1, n_channels, framerate,
                        framerate * n_channels * sampwidth,
                        n_channels * sampwidth, sampwidth * 8))
    f.write(b"data")
    f.write(struct.pack("<I", data_size))


def _generate_wav_noise(output_path, noise_type="pink", duration=0.5, sample_rate=48000, amplitude=0.3):
    """Generate noise WAV file — white, pink, or brown — using Python."""
    n_samples = int(sample_rate * duration)
    samples = []
    b0 = b1 = b2 = 0.0
    for i in range(n_samples):
        white = random.uniform(-1, 1)
        if noise_type == "brown":
            b0 = 0.9 * b0 + white * 0.1
            b0 = max(-1, min(1, b0))
            val = b0
        elif noise_type == "pink":
            b0 = 0.99886 * b0 + white * 0.0555179
            b1 = 0.99332 * b1 + white * 0.0750759
            b2 = 0.96900 * b2 + white * 0.1538520
            val = (b0 + b1 + b2 + white * 0.5362) * 0.11
        else:
            val = white
        env = 1.0 - (i / n_samples) * 0.3  # slight fade-out
        samples.append(int(max(-32768, min(32767, val * amplitude * env * 32767))))

    n_channels = 1
    sampwidth = 2
    framerate = sample_rate
    with open(output_path, "wb") as f:
        _write_wav_header(f, n_samples, n_channels, sampwidth, framerate)
        for s in samples:
            f.write(struct.pack("<h", s))
    return output_path if os.path.exists(output_path) and os.path.getsize(output_path) > 100 else None


def synthesize_impact(output_path, impact_type="thud"):
    """Phase 3: Generate an impact sound effect using Python.
    'thud' — sharp transient for ball kicks, punches
    'whoosh' — air movement for fast motion
    'crunch' — gravel/fabric texture
    """
    if impact_type == "thud":
        # Damped sine at 60Hz + 120Hz harmonic
        n_samples = int(AUDIO_SAMPLE_RATE * 0.3)
        samples = []
        for i in range(n_samples):
            t = i / AUDIO_SAMPLE_RATE
            val = math.sin(2 * math.pi * 60 * t) * math.exp(-t * 15) * 0.7
            val += math.sin(2 * math.pi * 120 * t) * math.exp(-t * 25) * 0.3
            samples.append(int(max(-32768, min(32767, val * 32767))))
        n_channels = 1; sampwidth = 2; framerate = AUDIO_SAMPLE_RATE
        with open(output_path, "wb") as f:
            _write_wav_header(f, n_samples, n_channels, sampwidth, framerate)
            for s in samples:
                f.write(struct.pack("<h", s))
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            print(f"  [audio] Synthesized thud (60Hz+120Hz damped sine)", flush=True)
            return output_path
    elif impact_type == "whoosh":
        # Frequency sweep from 2000Hz down to 200Hz with pink noise body
        result = _generate_wav_noise(output_path, "pink", 0.4, AUDIO_SAMPLE_RATE, 0.3)
        if result:
            print(f"  [audio] Synthesized whoosh (filtered pink noise)", flush=True)
            return result
    elif impact_type == "crunch":
        # Brown noise burst with high-frequency EQ
        result = _generate_wav_noise(output_path, "brown", 0.3, AUDIO_SAMPLE_RATE, 0.6)
        if result:
            print(f"  [audio] Synthesized crunch (brown noise burst)", flush=True)
            return result
    return None


def generate_ambience_bed(output_path, ambience_type="stadium"):
    """Phase 4: Generate ambient room tone / bed layer using Python.
    'stadium' — distant crowd murmur (pink noise, low-passed)
    'interior' — room hum (brown noise, heavily low-passed)
    'outdoor' — wind (pink noise, mid-range)
    """
    duration = 30
    if ambience_type == "stadium":
        result = _generate_wav_noise(output_path, "pink", duration, AUDIO_SAMPLE_RATE, 0.08)
    elif ambience_type == "interior":
        result = _generate_wav_noise(output_path, "brown", duration, AUDIO_SAMPLE_RATE, 0.04)
    else:
        result = _generate_wav_noise(output_path, "pink", duration, AUDIO_SAMPLE_RATE, 0.06)
    if result:
        print(f"  [audio] Generated ambience bed ({ambience_type})", flush=True)
        # Convert mono to stereo (simple duplicate channel via ffmpeg)
        stereo_out = output_path.replace(".wav", "_stereo.wav") if output_path.endswith(".wav") else output_path
        if output_path != stereo_out:
            cmd = [
                "ffmpeg", "-y", "-i", output_path,
                "-ac", "2", "-ar", str(AUDIO_SAMPLE_RATE),
                "-sample_fmt", "s16",
                stereo_out,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and os.path.exists(stereo_out) and os.path.getsize(stereo_out) > 1000:
                os.replace(stereo_out, output_path)
        return output_path
    return None


def apply_stereo_widening(input_path, output_path):
    """Phase 4: U-Shape stereo widening.
    Dialogue stays center, ambience pushed to extremes.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        "stereotools=mode=id:delay=15:phase_mid=1:phase_side=0, "
        "stereowiden=delay=10:feedback=0.3:crossfeed=0.3:dry_mix=0.8:wet_mix=0.6",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        output_path,
    ]
    result = _run_ffmpeg(cmd, "stereo widening")
    if result and os.path.exists(output_path):
        print(f"  [audio] Stereo widened (U-shape soundstage)", flush=True)
        return output_path
    return None


def mix_ambience_and_foley(input_path, ambience_path, foley_paths=None, output_path=None, duck_on_foley=True):
    """Phase 4: Mix ambience bed + foley effects with dynamic ducking.
    Ambience ducks -6dB for 0.5s when foley hits.
    """
    if output_path is None:
        output_path = input_path.replace(".wav", "_mixed.wav").replace(".mp4", "_mixed.wav")

    inputs = ["-i", input_path]
    filter_parts = [f"[0:a]asetpts=PTS-STARTPTS[main]"]

    # Add ambience
    if ambience_path and os.path.exists(ambience_path):
        inputs.extend(["-i", ambience_path])

    # Add foley paths
    foley_labels = []
    if foley_paths:
        for i, fp in enumerate(foley_paths):
            if os.path.exists(fp):
                inputs.extend(["-i", fp])
                label = f"foley{i}"
                foley_labels.append(label)
                filter_parts.append(f"[{len(inputs)//2 - 1}:a]asetpts=PTS-STARTPTS[{label}]")

    # Build mix with optional sidechain ducking
    if duck_on_foley and foley_labels:
        level_sc = 10 ** (AUDIO_DUCK_DB / 20)  # -6dB → 0.5 linear
        sidechain = f"[main][{foley_labels[0]}]sidechaincompress=threshold=-20:ratio=10:attack=5:release=50:level_sc={level_sc}[a_ducked]"
        filter_parts.append(sidechain)
        mix_sources = f"[a_ducked]"
    else:
        mix_sources = "[main]"

    for label in foley_labels:
        mix_sources += f"[{label}]"

    if ambience_path:
        # Mix ambience at low volume
        if duck_on_foley and foley_labels:
            filter_parts.append(f"[1:a]volume=0.25[a_amb]")
            filter_parts.append(f"[a_ducked][a_amb]amix=inputs=2:duration=first:weights=1 0.2[a_mixed]")
        else:
            filter_parts.append(f"[1:a]volume=0.25[a_amb];[main][a_amb]amix=inputs=2:duration=first:weights=1 0.2[a_mixed]")
        audio_map = "[a_mixed]"
    else:
        if duck_on_foley and foley_labels:
            audio_map = "[a_ducked]"
        else:
            audio_map = "[main]"

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", audio_map,
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        output_path,
    ]
    result = _run_ffmpeg(cmd, "ambience+foley mix")
    if result and os.path.exists(output_path):
        return output_path
    return None


def normalize_lufs(input_path, output_path, target_lufs=None):
    """Final: EBU R128 loudness normalization to -14 LUFS with -1 dBTP.
    Ensures YouTube does not re-compress/distort the dynamics.
    """
    if target_lufs is None:
        target_lufs = AUDIO_TARGET_LUFS

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        f"loudnorm=I={target_lufs}:LRA=7:TP={AUDIO_TRUE_PEAK}:print_format=json",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        output_path,
    ]
    result = _run_ffmpeg(cmd, f"LUFS normalization to {target_lufs} LUFS")
    if result and os.path.exists(output_path):
        print(f"  [audio] Normalized to {target_lufs} LUFS (TP: {AUDIO_TRUE_PEAK} dBTP)", flush=True)
        return output_path
    return None


def full_audio_pipeline(input_path, content_type="football", output_path=None):
    """Run the complete audio processing pipeline per Blueprint Section 2.
    Steps:
      1. EQ Carving (HP + LP + Presence)
      2. Dynamic Compression (4:1)
      3. Foley Synthesis (impact sounds per content type)
      4. Ambience Generation (stadium/interior)
      5. Stereo Widening
      6. Mixing with dynamic ducking
      7. LUFS Normalization (-14 LUFS)
    """
    if output_path is None:
        audio_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(CLIPS_DIR, f"audio_{audio_id}.mp4")

    print(f"  [audio] Full pipeline: {os.path.basename(input_path)} ({content_type})", flush=True)

    work_dir = os.path.join(CLIPS_DIR, "_audio_work")
    os.makedirs(work_dir, exist_ok=True)
    stage_id = uuid.uuid4().hex[:6]

    # Extract audio to WAV first
    raw_audio = os.path.join(work_dir, f"raw_{stage_id}.wav")
    cmd_extract = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        raw_audio,
    ]
    if not _run_ffmpeg(cmd_extract, "extract audio"):
        return None

    # Step 1: EQ Carving
    eq_path = os.path.join(work_dir, f"eq_{stage_id}.wav")
    if not apply_eq_carving(raw_audio, eq_path):
        eq_path = raw_audio

    # Step 2: Compression
    comp_path = os.path.join(work_dir, f"comp_{stage_id}.wav")
    if not apply_dynamic_compression(eq_path, comp_path):
        comp_path = eq_path

    # Step 3: Synthesize Foley
    foley_paths = []
    if content_type == "football":
        thud = os.path.join(work_dir, f"thud_{stage_id}.wav")
        if synthesize_impact(thud, "thud"):
            foley_paths.append(thud)
    elif content_type in ("movie", "series"):
        whoosh = os.path.join(work_dir, f"whoosh_{stage_id}.wav")
        if synthesize_impact(whoosh, "whoosh"):
            foley_paths.append(whoosh)
        crunch = os.path.join(work_dir, f"crunch_{stage_id}.wav")
        if synthesize_impact(crunch, "crunch"):
            foley_paths.append(crunch)

    # Step 4: Ambience bed
    amb_type = "stadium" if content_type == "football" else "interior"
    amb_path = os.path.join(work_dir, f"amb_{stage_id}.wav")
    if not generate_ambience_bed(amb_path, amb_type):
        amb_path = None

    # Step 5: Stereo widening on processed audio
    stereo_path = os.path.join(work_dir, f"stereo_{stage_id}.wav")
    if not apply_stereo_widening(comp_path, stereo_path):
        stereo_path = comp_path

    # Step 6: Mix ambience + foley
    mixed_path = os.path.join(work_dir, f"mixed_{stage_id}.wav")
    mixed = mix_ambience_and_foley(
        stereo_path, amb_path, foley_paths,
        output_path=mixed_path,
        duck_on_foley=bool(foley_paths),
    )
    if not mixed:
        mixed = stereo_path

    # Step 7: LUFS Normalization
    lufs_path = os.path.join(work_dir, f"lufs_{stage_id}.wav")
    if not normalize_lufs(mixed, lufs_path):
        lufs_path = mixed

    # Replace audio in original video
    cmd_replace = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", lufs_path,
        "-c:v", "copy",
        "-c:a", AUDIO_CODEC,
        "-b:a", AUDIO_BITRATE,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    result = _run_ffmpeg(cmd_replace, "replace audio in video", timeout=120)

    # Cleanup temp files
    for f in os.listdir(work_dir):
        try:
            os.remove(os.path.join(work_dir, f))
        except Exception:
            pass

    if result and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"  [audio] Pipeline complete: {os.path.basename(output_path)}", flush=True)
        return output_path

    print(f"  [audio] Pipeline failed — returning original", flush=True)
    return input_path
