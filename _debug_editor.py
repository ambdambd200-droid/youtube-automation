"""Debug clip editor to find why crop_to_shorts produces 0-byte files."""
import sys
import os
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from config import DOWNLOADS_DIR, CLIPS_DIR
from modules.clip_editor import remux_to_compatible, get_video_duration

# Find the largest webm in downloads
largest = None
largest_size = 0
for f in os.listdir(DOWNLOADS_DIR):
    fp = os.path.join(DOWNLOADS_DIR, f)
    if os.path.isfile(fp) and os.path.getsize(fp) > largest_size and not fp.endswith('.part'):
        largest_size = os.path.getsize(fp)
        largest = fp

print(f"Using: {largest} ({largest_size} bytes)")

if not largest:
    print("No downloaded files found")
    sys.exit(1)

# Re-mux first
working = remux_to_compatible(largest)
print(f"Working file: {working}")
dur = get_video_duration(working)
print(f"Duration: {dur}s")

# Simple test: just trim and scale
import uuid
clip_id = uuid.uuid4().hex[:10]
output = os.path.join(CLIPS_DIR, f"test_debug_{clip_id}.mp4")

print(f"Output: {output}")
print(f"File exists before ffmpeg: {os.path.exists(output)}")

cmd = [
    "ffmpeg", "-y",
    "-i", working,
    "-filter_complex",
    "[0:v]trim=start=5:duration=15,setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[vout];[0:a]atrim=start=5:duration=15,asetpts=PTS-STARTPTS[aout]",
    "-map", "[vout]",
    "-map", "[aout]",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "14",
    "-c:a", "aac",
    "-b:a", "128k",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "-movflags", "+faststart",
    output,
]

print(f"Running ffmpeg...", flush=True)
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
print(f"Return code: {proc.returncode}", flush=True)
if proc.returncode != 0:
    stderr_tail = proc.stderr[-2000:] if proc.stderr else "NO STDERR"
    print(f"STDERR (last 2000 chars): {stderr_tail}", flush=True)
    stdout_tail = proc.stdout[-500:] if proc.stdout else "NO STDOUT"
    print(f"STDOUT: {stdout_tail}", flush=True)
else:
    print(f"FFmpeg succeeded!", flush=True)

if os.path.exists(output):
    print(f"Output file exists: {os.path.getsize(output)} bytes", flush=True)
else:
    print("Output file does NOT exist!", flush=True)
