"""
Fetches images for YouTube videos from Wikipedia Commons and Pexels.
Call: python -m modules.image_fetcher --query "historical event" --count 5 --output-dir ./assets/images
"""

import argparse
import json
import os
import sys
import requests
import re
import random

sys.path.insert(0, ".")
from config import IMAGES_DIR, PEXELS_API_KEY

def get_wiki_session():
    """Get a requests session with proper headers for Wikipedia API."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "YouTubeAutomation/1.0 (n8n workflow; contact@example.com)",
        "Accept": "application/json"
    })
    return session

def fetch_wikipedia_images(query, max_images=5):
    """Fetch images from Wikipedia Commons related to a query."""
    images = []
    session = get_wiki_session()

    # Search English Wikipedia
    search_configs = [
        ("https://en.wikipedia.org/w/api.php", query),
    ]

    for search_url, search_query in search_configs:
        if len(images) >= max_images:
            break
        params = {
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "format": "json",
            "srlimit": 3
        }
        try:
            resp = session.get(search_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("search", [])

                for page in pages:
                    title = page.get("title", "")
                    if len(images) >= max_images:
                        break
                    img_params = {
                        "action": "query",
                        "titles": title,
                        "prop": "images",
                        "format": "json",
                        "imlimit": max_images - len(images)
                    }
                    img_resp = session.get(search_url, params=img_params, timeout=15)
                    if img_resp.status_code == 200:
                        img_data = img_resp.json()
                        pages_data = img_data.get("query", {}).get("pages", {})
                        for pid, pdata in pages_data.items():
                            for img in pdata.get("images", []):
                                if len(images) >= max_images:
                                    break
                                img_title = img.get("title", "")
                                if img_title.lower().endswith(('.jpg', '.png', '.jpeg', '.gif')):
                                    url_params = {
                                        "action": "query",
                                        "titles": img_title,
                                        "prop": "imageinfo",
                                        "iiprop": "url",
                                        "format": "json"
                                    }
                                    url_resp = session.get(search_url, params=url_params, timeout=15)
                                    if url_resp.status_code == 200:
                                        url_data = url_resp.json()
                                        for pid2, pdata2 in url_data.get("query", {}).get("pages", {}).items():
                                            for info in pdata2.get("imageinfo", []):
                                                img_url = info.get("url", "")
                                                if img_url:
                                                    images.append({
                                                        "url": img_url,
                                                        "title": img_title.replace("File:", ""),
                                                        "source": "wikipedia"
                                                    })
        except Exception as ex:
            print(f"Wikipedia fetch error for {search_url}: {ex}", file=sys.stderr)

    return images

def fetch_pexels_images(query, max_images=5):
    """Fetch images from Pexels API."""
    if not PEXELS_API_KEY:
        return []

    images = []
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": max_images}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for photo in data.get("photos", []):
                images.append({
                    "url": photo.get("src", {}).get("large", ""),
                    "title": query,
                    "source": "pexels",
                    "photographer": photo.get("photographer", "")
                })
    except Exception as ex:
        print(f"Pexels fetch error: {ex}", file=sys.stderr)

    return images

def download_image(img_info, output_dir, index):
    """Download an image from URL and save to disk."""
    url = img_info.get("url", "")
    if not url:
        return None

    ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".gif"]:
        ext = ".jpg"

    fname = f"img_{index:02d}{ext}"
    fpath = os.path.join(output_dir, fname)

    try:
        headers = {"User-Agent": "YouTubeAutomation/1.0 (n8n workflow)"}
        resp = requests.get(url, headers=headers, timeout=30, stream=True)
        if resp.status_code == 200:
            with open(fpath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return fpath
    except Exception as ex:
        print(f"Download error for {url}: {ex}", file=sys.stderr)

    return None

def extract_keywords_from_script(script):
    """Extract main keywords from a script for image search."""
    # Simple keyword extraction - take significant words
    words = re.findall(r'\w{4,}', script)
    # Filter common English stop words
    stop_words = {'this', 'that', 'these', 'those', 'with', 'from', 'have', 'been', 'were', 'what', 'when', 'where', 'which', 'their', 'there', 'could', 'would', 'should', 'about', 'after', 'before', 'between', 'through', 'during', 'without', 'because', 'just', 'then', 'also', 'more', 'some', 'them', 'than', 'very', 'still', 'over', 'such', 'each', 'other', 'into', 'only', 'much', 'many', 'most', 'like', 'well', 'even'}
    keywords = [w for w in words if w not in stop_words]

    # Count frequency and take top 10
    freq = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1

    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [kw for kw, _ in sorted_kw[:10]]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=None)
    parser.add_argument("--script-file", default=None)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    output_dir = args.output_dir or IMAGES_DIR
    os.makedirs(output_dir, exist_ok=True)

    query = args.query
    if not query and args.script_file:
        with open(args.script_file, "r", encoding="utf-8") as f:
            script = f.read()
        keywords = extract_keywords_from_script(script)
        query = " ".join(keywords[:3]) if keywords else "historical event"

    if not query:
        query = "historical event"

    # Fetch images from Wikipedia first, then Pexels as fallback
    all_images = fetch_wikipedia_images(query, args.count)

    if len(all_images) < args.count:
        pexel_images = fetch_pexels_images(query, args.count - len(all_images))
        all_images.extend(pexel_images)

    if not all_images:
        # Generate placeholder images with text
        result = {"error": "No images found", "files": []}
        print(json.dumps(result, ensure_ascii=False))
        return

    # Download images
    downloaded = []
    for i, img in enumerate(all_images[:args.count]):
        fpath = download_image(img, output_dir, i)
        if fpath:
            downloaded.append(fpath)

    result = {
        "query": query,
        "total_found": len(all_images),
        "downloaded": len(downloaded),
        "files": downloaded
    }
    print(json.dumps(result, ensure_ascii=False))

def fetch_commons_images(query, max_images=5):
    """Search Wikimedia Commons directly for images matching a query."""
    images = []
    session = get_wiki_session()

    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": "6",
            "format": "json",
            "srlimit": max_images * 2,
            "srprop": "snippet"
        }
        url = "https://commons.wikimedia.org/w/api.php"
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for page in data.get("query", {}).get("search", []):
                title = page.get("title", "")
                if any(title.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg', '.gif', '.svg']):
                    url_params = {
                        "action": "query",
                        "titles": title,
                        "prop": "imageinfo",
                        "iiprop": "url",
                        "format": "json"
                    }
                    url_resp = session.get(url, params=url_params, timeout=15)
                    if url_resp.status_code == 200:
                        for pid2, pdata2 in url_resp.json().get("query", {}).get("pages", {}).items():
                            for info in pdata2.get("imageinfo", []):
                                img_url = info.get("url", "")
                                if img_url:
                                    images.append({
                                        "url": img_url,
                                        "title": title.replace("File:", ""),
                                        "source": "commons"
                                    })
                                    if len(images) >= max_images:
                                        return images
    except Exception as ex:
        print(f"Commons fetch error: {ex}", file=sys.stderr)
    return images


def generate_placeholder_images(query, count=5, output_dir=None):
    """Generate simple placeholder images with text when no real images found."""
    from PIL import Image, ImageDraw, ImageFont

    out_dir = output_dir or IMAGES_DIR
    os.makedirs(out_dir, exist_ok=True)
    files = []

    # Color themes for placeholders
    themes = [
        (20, 15, 35), (35, 15, 25), (15, 25, 40),
        (40, 25, 15), (25, 35, 15), (15, 35, 35),
        (45, 20, 20), (20, 20, 45)
    ]

    for i in range(min(count, len(themes))):
        img = Image.new("RGB", (1920, 1080), themes[i])
        draw = ImageDraw.Draw(img)

        # Try to load a font (cross-platform: Windows + Linux)
        font = None
        for fp in [
            "C:\\Windows\\Fonts\\tahoma.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            None
        ]:
            try:
                font = ImageFont.truetype(fp, 80) if fp else ImageFont.load_default()
                break
            except:
                continue

        # Draw some decorative lines
        for j in range(5):
            y = 200 + j * 180
            draw.line([(100, y), (1820, y)], fill=(255, 255, 255, 30), width=1)

        # Draw topic text
        words = query.split()
        lines = []
        current = ""
        for w in words[:8]:
            if len(current) + len(w) < 20:
                current += " " + w if current else w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)

        if font:
            y = 400
            for li, line in enumerate(lines[:3]):
                bbox = draw.textbbox((0, 0), line, font=font)
                w = bbox[2] - bbox[0]
                draw.text(((1920 - w) // 2, y + li * 100), line, fill=(200, 200, 200), font=font)

        fpath = os.path.join(out_dir, f"bg_{i+1:02d}.jpg")
        img.save(fpath, "JPEG", quality=80)
        files.append(fpath)

    return files


def fetch_and_download_images(query=None, script=None, count=5, output_dir=None):
    """Fetch and download images for a given query or script."""
    out_dir = output_dir or IMAGES_DIR
    os.makedirs(out_dir, exist_ok=True)

    if not query and script:
        keywords = extract_keywords_from_script(script)
        query = " ".join(keywords[:3]) if keywords else "historical event"

    if not query:
        query = "historical event"

    # Try Commons first (most reliable for historical images)
    all_images = fetch_commons_images(query, count)

    # Fallback to Wikipedia
    if len(all_images) < count:
        wiki_images = fetch_wikipedia_images(query, count - len(all_images))
        all_images.extend(wiki_images)

    # Fallback to Pexels
    if len(all_images) < count:
        pexel_images = fetch_pexels_images(query, count - len(all_images))
        all_images.extend(pexel_images)

    downloaded = []
    for i, img in enumerate(all_images[:count]):
        fpath = download_image(img, out_dir, i)
        if fpath:
            downloaded.append(fpath)

    # If no images downloaded at all, generate placeholders
    if not downloaded:
        generated = generate_placeholder_images(query, count, out_dir)
        downloaded = generated

    return {
        "query": query,
        "total_found": len(all_images),
        "downloaded": len(downloaded),
        "files": downloaded
    }


if __name__ == "__main__":
    main()
