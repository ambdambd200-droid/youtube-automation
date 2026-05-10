"""
Generates YouTube thumbnails (3x2 photo collage style) using Pillow.
Call: python -m modules.thumbnail_generator --images img1.jpg img2.jpg --title "عنوان الفيديو" --output thumbnail.jpg
"""

import argparse
import json
import os
import sys
import math

sys.path.insert(0, ".")
from config import THUMBNAILS_DIR

def create_thumbnail(images, title, output_path, channel_logo_path=None):
    """Create a photo collage thumbnail inspired by [CHANNEL_A] style."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        result = {"error": "Pillow not installed", "output": None}
        print(json.dumps(result, ensure_ascii=False))
        return None

    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # YouTube thumbnail size: 1280x720
        thumb_width = 1280
        thumb_height = 720

        # Create dark background
        bg = Image.new("RGB", (thumb_width, thumb_height), (15, 15, 25))
        draw = ImageDraw.Draw(bg)

        if images and len(images) > 0:
            # Create 3x2 grid of images
            cols = 3
            rows = 2
            cell_w = thumb_width // cols
            cell_h = thumb_height // rows

            valid_images = []
            for img_path in images[:6]:
                if os.path.exists(img_path):
                    try:
                        img = Image.open(img_path)
                        # Crop to square then resize
                        min_dim = min(img.size)
                        left = (img.width - min_dim) // 2
                        top = (img.height - min_dim) // 2
                        img = img.crop((left, top, left + min_dim, top + min_dim))
                        img = img.resize((cell_w, cell_h), Image.LANCZOS)
                        valid_images.append(img)
                    except:
                        pass

            # Place images in grid
            for idx, img in enumerate(valid_images[:6]):
                r = idx // cols
                c = idx % cols
                x = c * cell_w
                y = r * cell_h
                # Add dark overlay
                overlay = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 80))
                img_with_overlay = img.copy()
                img_with_overlay.paste(overlay, (0, 0), overlay)
                bg.paste(img_with_overlay, (x, y))

            # Fill remaining cells with dark color
            for idx in range(len(valid_images), 6):
                r = idx // cols
                c = idx % cols
                x = c * cell_w
                y = r * cell_h
                draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(25, 25, 40))
        else:
            # Solid dark background with subtle gradient effect
            for i in range(thumb_height):
                shade = max(10, 30 - int(i * 20 / thumb_height))
                draw.line([(0, i), (thumb_width, i)], fill=(shade, shade, shade + 10))

        # Add title text
        if title:
            font_size = 55
            # Try to use an Arabic-capable font
            font_paths = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\tahoma.ttf",
                "C:\\Windows\\Fonts\\seguiemj.ttf",
                "C:\\Windows\\Fonts\\segoeui.ttf",
                None  # default
            ]

            font = None
            for fp in font_paths:
                try:
                    if fp:
                        font = ImageFont.truetype(fp, font_size)
                    else:
                        font = ImageFont.load_default()
                    break
                except:
                    continue

            if font is None:
                font = ImageFont.load_default()

            # Word wrap the title
            words = title.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] < thumb_width - 80:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            # Draw text with shadow
            for li, line in enumerate(lines[:3]):
                y_pos = thumb_height - 120 + li * 60 - (3 - len(lines[:3])) * 30
                text_bbox = draw.textbbox((0, 0), line, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x_pos = (thumb_width - text_width) // 2

                # Shadow
                draw.text((x_pos + 3, y_pos + 3), line, fill=(0, 0, 0), font=font)
                # Main text
                draw.text((x_pos, y_pos), line, fill=(255, 255, 255), font=font)

        # Add channel logo watermark if provided
        if channel_logo_path and os.path.exists(channel_logo_path):
            try:
                logo = Image.open(channel_logo_path)
                logo = logo.resize((80, 80), Image.LANCZOS)
                bg.paste(logo, (thumb_width - 100, 20), logo if logo.mode == 'RGBA' else None)
            except:
                pass

        bg.save(output_path, "JPEG", quality=95)
        return output_path

    except Exception as ex:
        print(f"Thumbnail error: {ex}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", default=[])
    parser.add_argument("--title", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--logo", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    images = args.images
    title = args.title
    output_path = args.output

    if args.json:
        data = json.loads(args.json)
        images = data.get("images", images)
        title = data.get("title", title)
        output_path = data.get("output", output_path)

    video_title = title or "فيديو جديد"
    thumb_path = create_thumbnail(images, video_title, output_path, args.logo)

    result = {
        "output": thumb_path,
        "title": video_title
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
