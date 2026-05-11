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
    """Create a professional YouTube thumbnail with dark theme."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        result = {"error": "Pillow not installed", "output": None}
        print(json.dumps(result, ensure_ascii=False))
        return None

    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        thumb_width = 1280
        thumb_height = 720

        bg = Image.new("RGB", (thumb_width, thumb_height), (10, 10, 20))
        draw = ImageDraw.Draw(bg)

        if images and len(images) > 0:
            cols = 3
            rows = 2
            cell_w = thumb_width // cols
            cell_h = thumb_height // rows

            valid_images = []
            for img_path in images[:6]:
                if os.path.exists(img_path):
                    try:
                        img = Image.open(img_path)
                        min_dim = min(img.size)
                        left = (img.width - min_dim) // 2
                        top = (img.height - min_dim) // 2
                        img = img.crop((left, top, left + min_dim, top + min_dim))
                        img = img.resize((cell_w, cell_h), Image.LANCZOS)
                        valid_images.append(img)
                    except:
                        pass

            for idx, img in enumerate(valid_images[:6]):
                r = idx // cols
                c = idx % cols
                x = c * cell_w
                y = r * cell_h
                overlay = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 100))
                img_with_overlay = img.copy()
                img_with_overlay.paste(overlay, (0, 0), overlay)
                bg.paste(img_with_overlay, (x, y))

            for idx in range(len(valid_images), 6):
                r = idx // cols
                c = idx % cols
                x = c * cell_w
                y = r * cell_h
                draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(20, 20, 35))
        else:
            for i in range(thumb_height):
                shade = max(8, 25 - int(i * 20 / thumb_height))
                draw.line([(0, i), (thumb_width, i)], fill=(shade, shade, shade + 8))

        # Bottom gradient overlay (darker at bottom for text readability)
        for i in range(thumb_height - 180, thumb_height):
            alpha = int(255 * (1 - (thumb_height - i) / 180))
            draw.line([(0, i), (thumb_width, i)], fill=(0, 0, 0, alpha))

        # Red accent line above text area
        accent_y = thumb_height - 200
        draw.rectangle([40, accent_y, thumb_width - 40, accent_y + 4], fill=(200, 40, 40))

        if title:
            font_size = 58
            font_paths = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\tahoma.ttf",
                "C:\\Windows\\Fonts\\seguiemj.ttf",
                "C:\\Windows\\Fonts\\segoeui.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-VariableFont_wdth,wght.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                None
            ]

            font = None
            for fp in font_paths:
                try:
                    font = ImageFont.truetype(fp, font_size) if fp else ImageFont.load_default()
                    break
                except:
                    continue

            if font is None:
                font = ImageFont.load_default()

            words = title.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] < thumb_width - 120:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            lines_to_show = lines[:2]

            for li, line in enumerate(lines_to_show):
                y_pos = thumb_height - 120 + li * 65
                text_bbox = draw.textbbox((0, 0), line, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x_pos = (thumb_width - text_width) // 2

                for ox, oy in [(3, 3), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    draw.text((x_pos + ox, y_pos + oy), line, fill=(0, 0, 0), font=font)
                draw.text((x_pos, y_pos), line, fill=(255, 255, 255), font=font)

        if channel_logo_path and os.path.exists(channel_logo_path):
            try:
                logo = Image.open(channel_logo_path)
                logo = logo.resize((60, 60), Image.LANCZOS)
                bg.paste(logo, (thumb_width - 80, 20), logo if logo.mode == 'RGBA' else None)
            except:
                pass

        # Channel watermark at bottom-left
        try:
            small_font = ImageFont.truetype(font_paths[0] if font_paths[0] else None, 20) if font else ImageFont.load_default()
            draw.text((20, thumb_height - 40), "@AlaaFathi", fill=(150, 150, 150), font=small_font if isinstance(small_font, ImageFont.ImageFont) else ImageFont.load_default())
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
