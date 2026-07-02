"""
Channel Branding Generator — creates channel profile picture and banner images.
Uses Pillow to generate VARY-branded graphics matching the channel's visual identity.

Profile Picture (800x800):
    - Stylized letter "V" merging a football goalpost on one side and a film strip on the other
    - Electric Blue or Dark Grey background with White or Gold logo
    - Clean, minimalist, readable at small sizes

Banner (2560x1440):
    - Dynamic split design: left side football / right side cinema
    - Dark background (Deep Blue/Black), White/Neon Yellow text
    - "VARY" centered in bold modern sans-serif
"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from config import CHANNEL_TAGLINE, OUTPUT_DIR

CHANNEL_ART_DIR = os.path.join(OUTPUT_DIR, "channel_art")


# ── Colour Palette ───────────────────────────────────────────
DEEP_BLUE = (10, 14, 40)       # Primary background
ELECTRIC_BLUE = (30, 80, 220)  # Accent
DARK_GREY = (25, 28, 35)       # Alternative background
WHITE = (255, 255, 255)
GOLD = (255, 200, 50)          # Accent / logo
NEON_YELLOW = (210, 230, 20)   # Alternative accent
SOFT_WHITE = (220, 220, 235)   # Body text
FOOTBALL_GREEN = (40, 180, 80) # Football accent
CINEMA_RED = (200, 40, 60)     # Cinema accent


def _get_font(size, bold=False):
    """Get a suitable font, falling back to default if none found."""
    import platform
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates = [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        ]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                pass
    return ImageFont.load_default()


# ── Profile Picture ──────────────────────────────────────────

def _draw_goalpost_film_v(draw, center, size, color):
    """Draw a bold stylised 'V' merging a football goalpost (left) with a film strip (right).

    Designed for the 800x800 circular crop — uses only bold, visible strokes
    (no fine details that get lost at small sizes).
    """
    radius = min(size) // 2 - 10
    cx, cy = center
    v_height = int(radius * 0.78)
    v_width = int(radius * 0.82)
    thickness = int(radius * 0.12)

    # ── Left leg — goalpost shape ──
    left_start = (cx - v_width, cy + int(v_height * 0.5))
    left_end = (cx - thickness, cy - int(v_height * 0.5))

    # Thick left leg stroke
    draw.line([left_start, left_end], fill=color, width=thickness)

    # Goalpost crossbar (bold horizontal near the top of the left leg)
    crossbar_y = left_end[1] + int(v_height * 0.18)
    crossbar_len = int(thickness * 3)
    draw.line(
        [left_end[0] - crossbar_len, crossbar_y, left_end[0] + crossbar_len, crossbar_y],
        fill=color,
        width=max(3, thickness // 2),
    )

    # ── Right leg — film strip shape ──
    right_start = (cx + v_width, cy + int(v_height * 0.5))
    right_end = (cx + thickness, cy - int(v_height * 0.5))

    draw.line([right_start, right_end], fill=color, width=thickness)

    # 3 large film sprocket holes (bold, visible at thumbnail size)
    for i in range(3):
        t = (i + 1) / 4
        hx = int(right_start[0] + (right_end[0] - right_start[0]) * t)
        hy = int(right_start[1] + (right_end[1] - right_start[1]) * t)
        hole_r = max(4, thickness // 2)
        draw.ellipse(
            [hx - hole_r, hy - hole_r, hx + hole_r, hy + hole_r],
            fill=(color[0], color[1], color[2], 200),
            outline=color,
            width=2,
        )

    # ── Bottom accent dot ──
    bottom_y = cy + int(v_height * 0.5) + int(thickness * 2)
    dot_r = max(4, thickness // 2)
    draw.ellipse(
        [cx - dot_r, bottom_y - dot_r, cx + dot_r, bottom_y + dot_r],
        fill=color,
    )


def create_profile_picture(size=(800, 800)):
    """Create a circular channel profile picture with the stylised V logo.

    Args:
        size: Tuple of (width, height) for the output image.

    Returns:
        Path to generated profile picture, or None on failure.
    """
    if not HAS_PILLOW:
        print("  [branding] Pillow not installed. Skipping profile picture generation.", flush=True)
        return None

    os.makedirs(CHANNEL_ART_DIR, exist_ok=True)
    output_path = os.path.join(CHANNEL_ART_DIR, "profile_picture.png")

    try:
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        center = (size[0] // 2, size[1] // 2)
        radius = min(size) // 2 - 10

        # ── Radial gradient background (Electric Blue → Deep Blue) ──
        for i in range(radius, 0, -1):
            ratio = i / radius
            r = int(ELECTRIC_BLUE[0] + (DEEP_BLUE[0] - ELECTRIC_BLUE[0]) * (1 - ratio))
            g = int(ELECTRIC_BLUE[1] + (DEEP_BLUE[1] - ELECTRIC_BLUE[1]) * (1 - ratio))
            b = int(ELECTRIC_BLUE[2] + (DEEP_BLUE[2] - ELECTRIC_BLUE[2]) * (1 - ratio))
            draw.ellipse(
                [center[0] - i, center[1] - i, center[0] + i, center[1] + i],
                fill=(r, g, b, 255),
            )

        # ── Outer glow ring ──
        glow_radius = int(radius * 0.95)
        for i in range(5, 0, -1):
            alpha = int(60 / i)
            draw.ellipse(
                [center[0] - glow_radius - i, center[1] - glow_radius - i,
                 center[0] + glow_radius + i, center[1] + glow_radius + i],
                outline=(GOLD[0], GOLD[1], GOLD[2], alpha),
                width=1,
            )

        # ── Goalpost + Film-strip V ──
        _draw_goalpost_film_v(draw, center, size, GOLD)

        # ── "VARY" text below the V ──
        font_tag = _get_font(int(radius * 0.13), bold=True)
        tag_text = "VARY"
        bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
        tw = bbox[2] - bbox[0]
        tag_y = center[1] + int(radius * 0.35)
        draw.text(
            (center[0] - tw // 2, tag_y),
            tag_text,
            fill=WHITE,
            font=font_tag,
        )

        img.save(output_path, "PNG")
        print(f"  [branding] Profile picture created: {output_path} ({os.path.getsize(output_path)} bytes)", flush=True)
        return output_path

    except Exception as e:
        print(f"  [branding] Profile picture error: {e}", flush=True)
        return None


# ── Banner ───────────────────────────────────────────────────

def _draw_football_side(draw, img_width, img_height):
    """Draw football-themed decorative elements on the left half of the banner."""
    cx = img_width * 0.2
    cy = img_height * 0.45

    # Stadium crowd glow (radial glow effect)
    for r in range(280, 80, -10):
        alpha = max(5, 40 - (280 - r) // 8)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(GOLD[0], GOLD[1], GOLD[2], alpha),
            width=1,
        )

    # Football (soccer ball) pattern
    ball_center = (int(cx), int(cy + 30))
    ball_r = 70
    draw.ellipse(
        [ball_center[0] - ball_r, ball_center[1] - ball_r,
         ball_center[0] + ball_r, ball_center[1] + ball_r],
        outline=WHITE,
        width=3,
    )
    # Pentagon hints on the ball
    pentagon_points = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        px = ball_center[0] + int(ball_r * 0.5 * math.cos(angle))
        py = ball_center[1] + int(ball_r * 0.5 * math.sin(angle))
        pentagon_points.append((px, py))
    if len(pentagon_points) == 5:
        draw.polygon(pentagon_points, outline=WHITE, width=2)

    # World Cup trophy — recognizable cup silhouette with handles
    trophy_x = int(img_width * 0.08)
    trophy_y = int(img_height * 0.22)
    # Trophy base
    base_w = 50
    base_h = 12
    draw.rectangle(
        [trophy_x - base_w // 2, trophy_y + 35, trophy_x + base_w // 2, trophy_y + 35 + base_h],
        fill=None,
        outline=GOLD,
        width=2,
    )
    # Trophy stem
    stem_w = 8
    stem_h = 20
    draw.rectangle(
        [trophy_x - stem_w // 2, trophy_y + 15, trophy_x + stem_w // 2, trophy_y + 15 + stem_h],
        fill=None,
        outline=GOLD,
        width=2,
    )
    # Trophy cup (two arcs forming a cup)
    cup_left = trophy_x - 22
    cup_right = trophy_x + 22
    cup_top = trophy_y
    cup_bottom = trophy_y + 18
    draw.arc([cup_left, cup_top, cup_right, cup_bottom], start=0, end=180, fill=GOLD, width=3)
    # Trophy handles (small arcs on each side)
    draw.arc([cup_left - 12, cup_top, cup_left, cup_bottom], start=270, end=90, fill=GOLD, width=2)
    draw.arc([cup_right, cup_top, cup_right + 12, cup_bottom], start=90, end=270, fill=GOLD, width=2)
    # Trophy glow
    for r in range(55, 10, -5):
        alpha = max(8, 30 - (55 - r) // 3)
        draw.ellipse(
            [trophy_x - r, trophy_y - r, trophy_x + r, trophy_y + r],
            fill=(GOLD[0], GOLD[1], GOLD[2], alpha),
        )

    # Stadium arch
    arch_center_x = int(img_width * 0.25)
    arch_center_y = int(img_height * 0.75)
    arch_r = 180
    draw.arc(
        [arch_center_x - arch_r, arch_center_y - arch_r,
         arch_center_x + arch_r, arch_center_y + arch_r],
        start=180, end=360,
        fill=(WHITE[0], WHITE[1], WHITE[2], 50),
        width=3,
    )


def _draw_cinema_side(draw, img_width, img_height):
    """Draw cinema-themed decorative elements on the right half of the banner."""
    cx = img_width * 0.8
    cy = img_height * 0.45

    # Film reel glow
    for r in range(280, 80, -10):
        alpha = max(5, 40 - (280 - r) // 8)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(CINEMA_RED[0], CINEMA_RED[1], CINEMA_RED[2], alpha),
            width=1,
        )

    # Film strip (vertical with bold sprocket holes on far right)
    strip_x = int(img_width * 0.92)
    hole_spacing = img_height // 12
    for i in range(12):
        hy = i * hole_spacing + hole_spacing // 2
        draw.rectangle(
            [strip_x - 10, hy - 14, strip_x + 10, hy + 14],
            outline=WHITE if i % 2 == 0 else GOLD,
            width=2,
        )

    # Clapperboard
    clap_cx = int(cx - 30)
    clap_cy = int(cy - 20)
    clap_w = 110
    clap_h = 85
    # Body
    draw.rectangle(
        [clap_cx - clap_w // 2, clap_cy - clap_h // 2,
         clap_cx + clap_w // 2, clap_cy + clap_h // 2],
        outline=WHITE,
        width=3,
    )
    # Diagonal top stick (open clapper)
    draw.line(
        [clap_cx - clap_w // 2 - 12, clap_cy - clap_h // 2 - 12,
         clap_cx + clap_w // 2 + 12, clap_cy + clap_h // 2 - int(clap_h * 0.25)],
        fill=WHITE,
        width=4,
    )
    # Stripes on clapperboard
    for i in range(4):
        sx = clap_cx - clap_w // 2 + 12 + i * 24
        draw.line(
            [sx, clap_cy - clap_h // 2 + 8, sx, clap_cy + clap_h // 2 - 8],
            fill=WHITE,
            width=2,
        )

    # Theatre mask silhouette (tragedy/comedy) — two overlapping ovals with eye slots
    mask_x = int(img_width * 0.72)
    mask_y = int(img_height * 0.72)
    # Left eye region of the mask
    draw.ellipse(
        [mask_x - 30, mask_y - 18, mask_x - 5, mask_y + 18],
        outline=SOFT_WHITE,
        width=2,
    )
    # Right eye region
    draw.ellipse(
        [mask_x + 5, mask_y - 18, mask_x + 30, mask_y + 18],
        outline=SOFT_WHITE,
        width=2,
    )
    # Mouth (slight curve underneath)
    draw.arc(
        [mask_x - 18, mask_y + 8, mask_x + 18, mask_y + 30],
        start=0, end=180,
        fill=SOFT_WHITE,
        width=2,
    )


def create_banner(size=(2560, 1440)):
    """Create a YouTube channel banner with split football/cinema design.

    YouTube banner dimensions: 2560x1440 (safe area: 1546x423 centered).

    Args:
        size: Tuple of (width, height) for the output image.

    Returns:
        Path to generated banner, or None on failure.
    """
    if not HAS_PILLOW:
        print("  [branding] Pillow not installed. Skipping banner generation.", flush=True)
        return None

    os.makedirs(CHANNEL_ART_DIR, exist_ok=True)
    output_path = os.path.join(CHANNEL_ART_DIR, "channel_banner.png")

    try:
        img = Image.new("RGB", size, DEEP_BLUE)
        draw = ImageDraw.Draw(img)

        # ── Background gradient (top-to-bottom dark blend) ──
        for y in range(size[1]):
            ratio = y / size[1]
            r = int(DEEP_BLUE[0] + (DARK_GREY[0] - DEEP_BLUE[0]) * (ratio * 0.3))
            g = int(DEEP_BLUE[1] + (DARK_GREY[1] - DEEP_BLUE[1]) * (ratio * 0.3))
            b = int(DEEP_BLUE[2] + (DARK_GREY[2] - DEEP_BLUE[2]) * (ratio * 0.3))
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))

        # ── Centre divider glow (subtle vertical gradient) ──
        div_x = size[0] // 2
        for x in range(div_x - 3, div_x + 3):
            alpha = max(0, 60 - abs(x - div_x) * 10)
            draw.line(
                [(x, 0), (x, size[1])],
                fill=(GOLD[0], GOLD[1], GOLD[2], alpha),
            )

        # ── Decorative halves ──
        _draw_football_side(draw, size[0], size[1])
        _draw_cinema_side(draw, size[0], size[1])

        # ── "VARY" title (safe centre area) ──
        font_large = _get_font(200, bold=True)
        v_text = "VARY"
        bbox = draw.textbbox((0, 0), v_text, font=font_large)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        center_x = size[0] // 2
        center_y = size[1] // 2 - 70

        # Title shadow for depth
        shadow_offset = 4
        draw.text(
            (center_x - tw // 2 + shadow_offset, center_y - th // 2 + shadow_offset),
            v_text,
            fill=(0, 0, 0, 180),
            font=font_large,
        )
        # Title main
        draw.text(
            (center_x - tw // 2, center_y - th // 2),
            v_text,
            fill=WHITE,
            font=font_large,
        )

        # ── Tagline ──
        font_medium = _get_font(50, bold=False)
        tagline = CHANNEL_TAGLINE
        bbox = draw.textbbox((0, 0), tagline, font=font_medium)
        tw = bbox[2] - bbox[0]
        tagline_y = center_y + 70
        draw.text(
            (center_x - tw // 2, tagline_y),
            tagline,
            fill=SOFT_WHITE,
            font=font_medium,
        )

        # ── Accent line below tagline ──
        line_y = tagline_y + 50
        line_width = 300
        draw.rectangle(
            [center_x - line_width // 2, line_y, center_x + line_width // 2, line_y + 3],
            fill=NEON_YELLOW,
        )

        # ── Emoji labels flanking the centre ──
        font_emoji = _get_font(80, bold=False)
        # Left: ⚽ football
        emoji_text = "⚽"
        bbox = draw.textbbox((0, 0), emoji_text, font=font_emoji)
        ew = bbox[2] - bbox[0]
        draw.text(
            (center_x - tw // 2 - ew - 60, center_y - th // 2 - 10),
            emoji_text,
            fill=SOFT_WHITE,
            font=font_emoji,
        )
        # Right: 🎬 cinema
        draw.text(
            (center_x + tw // 2 + 30, center_y - th // 2 - 10),
            "🎬",
            fill=SOFT_WHITE,
            font=font_emoji,
        )

        # ── Subtle bottom tag: "VARY" watermark ──
        font_small = _get_font(28, bold=False)
        watermark = "VARY — Daily Clips"
        bbox = draw.textbbox((0, 0), watermark, font=font_small)
        ww = bbox[2] - bbox[0]
        draw.text(
            (size[0] - ww - 30, size[1] - 50),
            watermark,
            fill=(WHITE[0], WHITE[1], WHITE[2], 60),
            font=font_small,
        )

        img.save(output_path, "PNG")
        print(f"  [branding] Channel banner created: {output_path} ({os.path.getsize(output_path)} bytes)", flush=True)
        return output_path

    except Exception as e:
        print(f"  [branding] Banner error: {e}", flush=True)
        return None


# ── Entry Point ──────────────────────────────────────────────

def generate_all_branding():
    """Generate all channel branding assets (profile picture + banner)."""
    os.makedirs(CHANNEL_ART_DIR, exist_ok=True)

    profile = create_profile_picture()
    banner = create_banner()

    return {
        "profile_picture": profile,
        "banner": banner,
        "directory": CHANNEL_ART_DIR,
    }


if __name__ == "__main__":
    result = generate_all_branding()
    print(f"Profile picture: {result.get('profile_picture', 'FAILED')}")
    print(f"Banner: {result.get('banner', 'FAILED')}")
    print(f"Directory: {result['directory']}")
