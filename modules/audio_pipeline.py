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
    BGM_LUFS_TARGET, BGM_VOLUME, MUSICGEN_MODEL, MUSICGEN_TIMEOUT,
)


def _run_ffmpeg(cmd, description="audio", timeout=120):
    """Run ffmpeg and log."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            err = result.stderr[-500:] if result.stderr else "no stderr"
            print(f"  [audio] {description} failed (rc={result.returncode}): {err}", flush=True)
            return None
        return result
    except subprocess.TimeoutExpired:
        print(f"  [audio] {description} timed out ({timeout}s)", flush=True)
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
    # ffmpeg 8.1+ uses linear threshold (0-1), not dB — convert: 10^(-24/20) = 0.063
    thresh_linear = 0.063
    ratio = AUDIO_COMPRESSION_RATIO
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        f"acompressor=threshold={thresh_linear}:ratio={ratio}:attack=5:release=50:makeup=3",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        "-sample_fmt", "s16",
        output_path,
    ]
    result = _run_ffmpeg(cmd, f"compression {ratio}:1")
    if result and os.path.exists(output_path):
        print(f"  [audio] Compressed {ratio}:1 at {thresh_linear} linear threshold", flush=True)
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


def generate_ambience_bed(output_path, ambience_type="stadium", duration=30):
    """Phase 4: Generate ambient room tone / bed layer using Python.
    'stadium' — distant crowd murmur (pink noise, low-passed)
    'interior' — room hum (brown noise, heavily low-passed)
    'outdoor' — wind (pink noise, mid-range)
    """
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
        "stereowiden=delay=10:feedback=0.3:crossfeed=0.3:drymix=0.8",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        "-sample_fmt", "s16",
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
    next_stream = 1

    has_ambience = ambience_path and os.path.exists(ambience_path)
    valid_foley = [fp for fp in (foley_paths or []) if os.path.exists(fp)]
    has_foley = len(valid_foley) > 0

    # Add ambience
    if has_ambience:
        inputs.extend(["-i", ambience_path])
        filter_parts.append(f"[{next_stream}:a]volume=0.25[a_amb]")
        next_stream += 1

    # Add foley paths with labels
    foley_labels = []
    for i, fp in enumerate(valid_foley):
        inputs.extend(["-i", fp])
        label = f"f{i}"
        foley_labels.append(label)
        filter_parts.append(f"[{next_stream}:a]asetpts=PTS-STARTPTS[{label}]")
        next_stream += 1

    # Build filter graph
    if has_foley:
        # Sidechain: duck main audio when foley hits
        if duck_on_foley:
            level_sc = 10 ** (AUDIO_DUCK_DB / 20)
            sc_thresh = 0.1
            filter_parts.append(
                f"[main][{foley_labels[0]}]"
                f"sidechaincompress=threshold={sc_thresh}:ratio=10:"
                f"attack=5:release=50:level_sc={level_sc}[a_ducked]"
            )
            main_src = "[a_ducked]"
        else:
            main_src = "[main]"

        # Mix main + all foley + ambience
        mix_inputs = main_src + "".join(f"[{l}]" for l in foley_labels)
        mix_count = 1 + len(foley_labels)
        weights = "1" + " ".join(f" {0.5 if i == 0 else 0.3}" for i in range(len(foley_labels)))
        if has_ambience:
            mix_inputs += "[a_amb]"
            mix_count += 1
            weights += " 0.2"
        filter_parts.append(
            f"{mix_inputs}amix=inputs={mix_count}:duration=first:"
            f"weights={weights}[a_mixed]"
        )
        audio_map = "[a_mixed]"
    else:
        # No foley — just mix main + ambience
        if has_ambience:
            filter_parts.append("[main][a_amb]amix=inputs=2:duration=first:weights=1 0.2[a_mixed]")
            audio_map = "[a_mixed]"
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


def generate_background_music(output_path, content_type="football", duration=30):
    """Generate ambient background music using ffmpeg synthesis filters.
    No external dependencies — built-in ffmpeg audio generation.
    Creates content-type-specific musical beds:
    - football: low brass drone + rhythmic pulse
    - movie: ambient strings pad
    - series: soft piano-like tone
    """
    duration = max(15, int(duration))
    if content_type == "football":
        filter_complex = (
            "anoisesrc=d={}:c=pink:a=0.15,lowpass=f=400,volume=0.8[s1];"
            "sine=f=65:d={}[b0];"
            "sine=f=130:d={}[h0];"
            "[b0]volume=0.1[bass];"
            "[h0]volume=0.05[harm];"
            "[s1][bass][harm]amix=inputs=3:duration=first:weights=0.5 0.3 0.2[a]"
        ).format(duration, duration, duration)
    elif content_type == "series":
        filter_complex = (
            "anoisesrc=d={}:c=brown:a=0.1,lowpass=f=200,volume=0.6[s1];"
            "sine=f=55:d={}[b0];"
            "sine=f=165:d={}[h0];"
            "[b0]volume=0.08[bass];"
            "[h0]volume=0.04[harm];"
            "[s1][bass][harm]amix=inputs=3:duration=first:weights=0.4 0.4 0.2[a]"
        ).format(duration, duration, duration)
    else:
        filter_complex = (
            "anoisesrc=d={}:c=pink:a=0.12,lowpass=f=300,volume=0.7[s1];"
            "sine=f=60:d={}[b0];"
            "[b0]volume=0.09[bass];"
            "[s1][bass]amix=inputs=2:duration=first:weights=0.6 0.4[a]"
        ).format(duration, duration)

    cmd = [
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[a]",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        "-sample_fmt", "s16",
        output_path,
    ]
    result = _run_ffmpeg(cmd, f"BGM generation ({content_type})", timeout=60)
    if result and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
        print(f"  [audio] BGM generated: {content_type} ambient bed ({duration}s)", flush=True)
        return output_path
    return None


def generate_musicgen_bgm(output_path, content_type="football", duration=30):
    """Generate BGM using MusicGen (Meta) if available.

    Falls back gracefully if dependencies are missing.
    """
    prompt_map = {
        "football": "epic sports orchestral build-up, low brass, tension, no drums, cinematic",
        "movie": "cinematic ambient strings, mysterious, building tension, slow, orchestral",
        "series": "emotional piano, subtle strings, intimate, gentle, dramatic",
    }
    prompt = prompt_map.get(content_type, "ambient cinematic texture, atmospheric")
    duration = min(max(15, int(duration)), 60)

    try:
        import torch
        from audiocraft.models import MusicGen
        import scipy.io.wavfile
    except ImportError:
        print(f"  [audio] MusicGen not available (install: pip install audiocraft scipy)", flush=True)
        return None

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"  [audio] Loading MusicGen ({MUSICGEN_MODEL}) on {device}...", flush=True)
            model = MusicGen.get_pretrained(MUSICGEN_MODEL, device=device)
            model.set_generation_params(duration=duration)
            print(f"  [audio] Generating BGM: '{prompt}' ({duration}s)...", flush=True)
            wav = model.generate([prompt], progress=True)
            sr = 32000
            if hasattr(model, 'sample_rate'):
                sr = model.sample_rate
            scipy.io.wavfile.write(output_path, rate=sr, data=wav[0].cpu().numpy().T)
            print(f"  [audio] MusicGen BGM saved: {output_path}", flush=True)
            return output_path
    except Exception as e:
        print(f"  [audio] MusicGen failed: {e}", flush=True)
        return None


def apply_master_bus(input_path, output_path):
    """Master bus processing: multiband dynamics + limiter.

    Even out frequency imbalances, then catch true peaks.
    Uses ffmpeg's acompressor + loudnorm (already in the pipeline).
    Adds an extra compand stage for glue compression.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        "compand=attacks=0.1:decays=0.5:"
        "points=-80/-80|-30/-20|-12/-8|0/-2:"
        "gain=1,alimiter=limit=-1.0:attack=0.1:release=1.0",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
        output_path,
    ]
    result = _run_ffmpeg(cmd, "master bus compression")
    if result and os.path.exists(output_path):
        print(f"  [audio] Master bus: gentle glue + limiter (-1 dBTP)", flush=True)
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

    # Step 4: Background Music (BGM)
    clip_duration = 30
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            clip_duration = max(15, float(r.stdout.strip()))
    except Exception:
        pass

    bgm_path = os.path.join(work_dir, f"bgm_{stage_id}.wav")
    bgm = generate_musicgen_bgm(bgm_path, content_type, duration=int(clip_duration))
    if not bgm:
        bgm = generate_background_music(bgm_path, content_type, duration=int(clip_duration))
    if bgm:
        # Normalize BGM to -24 LUFS
        bgm_norm = os.path.join(work_dir, f"bgm_norm_{stage_id}.wav")
        if normalize_lufs(bgm, bgm_norm, target_lufs=BGM_LUFS_TARGET):
            bgm = bgm_norm
        print(f"  [audio] BGM ready: {os.path.basename(bgm)}", flush=True)

    # Step 5: Ambience bed (match clip duration)
    amb_type = "stadium" if content_type == "football" else "interior"
    amb_path = os.path.join(work_dir, f"amb_{stage_id}.wav")
    if not generate_ambience_bed(amb_path, amb_type, duration=clip_duration):
        amb_path = None

    # Step 6: Mix ambience + foley
    mixed_no_bgm_path = os.path.join(work_dir, f"mixed_{stage_id}.wav")
    mixed_no_bgm = mix_ambience_and_foley(
        comp_path, amb_path, foley_paths,
        output_path=mixed_no_bgm_path,
        duck_on_foley=bool(foley_paths),
    )
    if not mixed_no_bgm:
        mixed_no_bgm = comp_path

    # Step 7: Mix in BGM
    if bgm and os.path.exists(bgm):
        mixed_path = os.path.join(work_dir, f"mixed_with_bgm_{stage_id}.wav")
        inputs = ["-i", mixed_no_bgm, "-i", bgm]
        filter_parts = (
            f"[0:a]asetpts=PTS-STARTPTS[main];"
            f"[1:a]volume=1.0[bgm];"
            f"[main][bgm]amix=inputs=2:duration=first:"
            f"weights=1 {BGM_VOLUME}"
        )
        cmd_mix = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_parts,
            "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2",
            mixed_path,
        ]
        result = _run_ffmpeg(cmd_mix, "mix BGM into audio")
        if result and os.path.exists(mixed_path):
            final_mixed = mixed_path
        else:
            final_mixed = mixed_no_bgm
    else:
        final_mixed = mixed_no_bgm

    # Step 8: Stereo widening on final mix
    stereo_path = os.path.join(work_dir, f"stereo_{stage_id}.wav")
    if not apply_stereo_widening(final_mixed, stereo_path):
        stereo_path = final_mixed

    # Step 9: Master bus (glue compression + limiter)
    master_path = os.path.join(work_dir, f"master_{stage_id}.wav")
    if not apply_master_bus(stereo_path, master_path):
        master_path = stereo_path

    # Step 10: LUFS Normalization
    lufs_path = os.path.join(work_dir, f"lufs_{stage_id}.wav")
    if not normalize_lufs(master_path, lufs_path):
        lufs_path = master_path

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
