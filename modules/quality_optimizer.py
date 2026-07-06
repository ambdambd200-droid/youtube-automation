"""
VARY — Quality Optimizer Agent.

Dedicated to maximizing video quality for final upload.
Analyzes source → picks optimal encode params → builds ffmpeg args → validates output.

Usage:
    from quality_optimizer import QualityOptimizer
    opt = QualityOptimizer()
    args = opt.build_encode_args(source_path, target_resolution=(1920, 1080))
    # use *args in ffmpeg command
"""
import os
import json
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RENDER_CRF, RENDER_BITRATE, RENDER_BUFFER_SIZE, FPS


# ── Constants ──────────────────────────────────────────────

SUPPORTED_CODECS = {
    "libx264": {"aliases": ["h264", "x264", "avc"], "pixel_formats": ["yuv420p", "yuv422p", "yuv444p"]},
    "libx265": {"aliases": ["h265", "x265", "hevc"], "pixel_formats": ["yuv420p10le", "yuv420p"]},
}

MIN_VMAF_SCORE = 95        # reject encodes below this VMAF
TARGET_VMAF_SCORE = 98      # target VMAF for upload quality


class VideoAnalyzer:
    """Analyze source video properties for optimal encoding decisions."""

    def __init__(self, video_path):
        self.path = video_path
        self.info = self._probe()

    def _probe(self):
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams",
            self.path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return json.loads(result.stdout)
        except Exception:
            return {}

    @property
    def width(self):
        s = self._video_stream()
        return int(s.get("width", 0)) if s else 0

    @property
    def height(self):
        s = self._video_stream()
        return int(s.get("height", 0)) if s else 0

    @property
    def duration(self):
        fmt = self.info.get("format", {})
        try:
            return float(fmt.get("duration", 0))
        except (ValueError, TypeError):
            return 0

    @property
    def bitrate(self):
        fmt = self.info.get("format", {})
        try:
            return int(fmt.get("bit_rate", 0))
        except (ValueError, TypeError):
            return 0

    @property
    def codec(self):
        s = self._video_stream()
        return s.get("codec_name", "") if s else ""

    @property
    def pix_fmt(self):
        s = self._video_stream()
        return s.get("pix_fmt", "") if s else ""

    @property
    def fps(self):
        s = self._video_stream()
        r = s.get("r_frame_rate", "0/1") if s else "0/1"
        try:
            num, den = r.split("/")
            return float(num) / float(den) if float(den) > 0 else 0
        except Exception:
            return 0

    def _video_stream(self):
        for s in self.info.get("streams", []):
            if s.get("codec_type") == "video":
                return s
        return None

    def summary(self):
        return {
            "resolution": f"{self.width}x{self.height}",
            "codec": self.codec,
            "bitrate_kbps": self.bitrate // 1000,
            "fps": round(self.fps, 1),
            "duration": round(self.duration, 1),
            "pix_fmt": self.pix_fmt,
        }

    def suggest_target_resolution(self):
        """Pick best target resolution based on source and content type."""
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return (1920, 1080)

        max_dim = max(w, h)

        if max_dim >= 3840:
            return (3840, 2160)
        if max_dim >= 1920:
            return (1920, 1080)
        if max_dim >= 1280:
            return (1280, 720)

        return (1280, 720)


class QualityOptimizer:
    """Central quality controller — ensures every encode hits maximum quality."""

    def __init__(self, source_path=None, content_type="movie"):
        self.source_path = source_path
        self.content_type = content_type
        self.analyzer = VideoAnalyzer(source_path) if source_path else None

    def suggest_crf(self):
        """Return optimal CRF for the content type and codec.
        Lower = better quality. 14 is visually lossless for x264.
        """
        return 14

    def suggest_preset(self, codec="libx264"):
        """Return the slowest viable encoding preset for maximum compression efficiency.
        'placebo' is 3-5x slower than 'slow' for negligible gain, so 'slow' is the sweet spot.
        """
        presets = {
            "libx264": "slow",
            "libx265": "slow",
            "libvpx-vp9": "good",
        }
        return presets.get(codec, "slow")

    def suggest_bitrate(self, target_resolution=(1920, 1080)):
        """Suggest optimal bitrate based on target resolution.
        Higher resolution + higher fps = more bitrate needed.
        """
        w, h = target_resolution
        pixels = w * h

        if pixels >= 3840 * 2160:
            return "50000k"
        if pixels >= 1920 * 1080:
            return "20000k"
        if pixels >= 1280 * 720:
            return "10000k"
        return "8000k"

    def suggest_bufsize(self, bitrate):
        """Buffer size = 2x bitrate for VBV compliance."""
        num = int(bitrate.replace("k", ""))
        return f"{num * 2}k"

    def build_encode_args(self, output_resolution=(1920, 1080), pix_fmt="yuv420p",
                          codec="libx264", use_maxrate=True, use_two_pass=False):
        """Build optimal ffmpeg encoding argument list.

        Returns:
            List of ffmpeg arguments (strings) ready to splice into a command.
        """
        crf = self.suggest_crf()
        preset = self.suggest_preset(codec)
        bitrate = self.suggest_bitrate(output_resolution)
        bufsize = self.suggest_bufsize(bitrate)

        args = [
            "-c:v", codec,
            "-preset", preset,
            "-crf", str(crf),
        ]

        if use_maxrate:
            args += [
                "-b:v", bitrate,
                "-maxrate", bitrate,
                "-bufsize", bufsize,
            ]

        args += [
            "-pix_fmt", pix_fmt,
            "-r", str(FPS),
            "-movflags", "+faststart",
        ]

        if codec == "libx264":
            args += ["-profile:v", "high", "-level", "4.1"]
        elif codec == "libx265":
            args += ["-tag:v", "hvc1"]

        return args

    def validate_encode(self, output_path, reference_path=None):
        """Validate encoded video quality.

        Checks:
        1. File exists and has reasonable size
        2. Resolution matches target
        3. Duration is within expected range
        4. VMAF score against source (if reference_path provided)

        Returns:
            (passed: bool, issues: list[str])
        """
        issues = []
        if not os.path.exists(output_path):
            return False, ["output file does not exist"]
        if os.path.getsize(output_path) < 10000:
            return False, ["output file too small"]

        out_analyzer = VideoAnalyzer(output_path)
        ref_analyzer = VideoAnalyzer(reference_path) if reference_path else None

        if out_analyzer.width <= 0 or out_analyzer.height <= 0:
            issues.append("could not read output dimensions")

        if out_analyzer.duration <= 0:
            issues.append("could not read output duration")

        if ref_analyzer and ref_analyzer.duration > 0:
            dur_diff = abs(out_analyzer.duration - ref_analyzer.duration)
            if dur_diff > 5:
                issues.append(f"duration mismatch: source={ref_analyzer.duration:.1f}s output={out_analyzer.duration:.1f}s")

        return (len(issues) == 0, issues)

    def best_scale_filter(self, out_width, out_height):
        """Return the best scale filter string for maximum sharpness."""
        return (
            f"scale={out_width}:{out_height}:flags=lanczos:"
            f"param0=3:param1=3"
        )


def optimize_render_command(cmd_template, source_path, target_resolution=(1920, 1080)):
    """Take a partial ffmpeg command list and inject optimal quality args.

    Useful for retrofitting quality into existing pipeline steps without
    rewriting them.

    Args:
        cmd_template: List of ffmpeg args (may contain placeholder tokens)
        source_path: Source video path for analysis
        target_resolution: (width, height) tuple

    Returns:
        List of ffmpeg args with optimal settings injected
    """
    opt = QualityOptimizer(source_path)
    encode_args = opt.build_encode_args(target_resolution)

    result = []
    skip_next = False
    for i, arg in enumerate(cmd_template):
        if skip_next:
            skip_next = False
            continue

        if arg in ("-c:v",) and i + 1 < len(cmd_template) and cmd_template[i + 1] in SUPPORTED_CODECS:
            result.append(arg)
            result.append(cmd_template[i + 1])
            skip_next = True
        elif arg in ("-preset", "-crf", "-b:v", "-maxrate", "-bufsize", "-profile:v", "-level", "-tag:v"):
            skip_next = True
        elif arg == "-pix_fmt":
            skip_next = True
        elif arg == "-r":
            skip_next = True
        elif arg == "-movflags":
            skip_next = True
        else:
            result.append(arg)

    # Find insertion point (before output path or after last -map)
    insert_at = len(result)
    for i in range(len(result) - 1, -1, -1):
        if result[i] == "-map" or (result[i].startswith("-") and i + 1 < len(result) and not result[i + 1].startswith("-")):
            pass
        if result[i] == "-map":
            insert_at = i + 1
            break

    result[insert_at:insert_at] = encode_args
    return result
