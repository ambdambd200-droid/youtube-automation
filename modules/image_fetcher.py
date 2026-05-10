"""
Fetches images for YouTube videos from Wikipedia Commons and/or Pexels.
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

    # Try Arabic Wikipedia first, then English
    search_configs = [
        ("https://ar.wikipedia.org/w/api.php", query),
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
    params = {"query": query, "per_page": max_images, "locale": "ar-SA"}

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
    """Extract main keywords from an Arabic script for image search."""
    # Simple keyword extraction - take significant words
    words = re.findall(r'\w{4,}', script)
    # Filter common Arabic stop words
    stop_words = {'هذا', 'هذه', 'ذلك', 'كان', 'على', 'عن', 'في', 'من', 'إلى', 'مع', 'ما', 'لا', 'إن', 'أن', 'قد', 'كل', 'بعض', 'هو', 'هي', 'هم', 'كانت', 'يكون', 'يكونون', 'ليس', 'ولكن', 'أو', 'إذا', 'حتى', 'عند', 'بعد', 'قبل', 'فقط', 'كما', 'لقد', 'سوف', 'ثم', 'حين', 'بين', 'تحت', 'فوق', 'دون', 'غير'}
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

def fetch_and_download_images(query=None, script=None, count=5, output_dir=None):
    """Fetch and download images for a given query or script."""
    out_dir = output_dir or IMAGES_DIR
    os.makedirs(out_dir, exist_ok=True)

    if not query and script:
        keywords = extract_keywords_from_script(script)
        query = " ".join(keywords[:3]) if keywords else "historical event"

    if not query:
        query = "historical event"

    all_images = fetch_wikipedia_images(query, count)

    if len(all_images) < count:
        pexel_images = fetch_pexels_images(query, count - len(all_images))
        all_images.extend(pexel_images)

    downloaded = []
    for i, img in enumerate(all_images[:count]):
        fpath = download_image(img, out_dir, i)
        if fpath:
            downloaded.append(fpath)

    return {
        "query": query,
        "total_found": len(all_images),
        "downloaded": len(downloaded),
        "files": downloaded
    }


if __name__ == "__main__":
    main()
